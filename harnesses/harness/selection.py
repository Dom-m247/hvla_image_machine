"""Source name -> every runnable pre-EVLA observation, and its archive files on disk.

One radio_search2 SSH session serves the whole selection, and the result is
written to a manifest so the (slow, network-bound) selection phase can be done
once and the pipeline phase re-run against it as often as you like. Which of the
runnable observations a sweep keeps is up to the harness kind (harness/kinds/).
"""
import contextlib
import io
import json
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from .pipeline import (
  BAND_GHZ_RANGES, CLI, DelosDownload, NED_API, Options, PRE_EVLA_YEAR,
  RadioSearchIntegration, parseArchFileInfo, sensitivity_jy, size_mb,
)

#radio_search2 writes Ku band as 'U' in some rows; every other band code it emits
#already matches the pipeline's band tables. Bands outside those tables (4, P)
#have no spw range or angular-resolution entry, so a run on one cannot be sized.
BAND_ALIASES = {'U': 'Ku'}

#NED_API.obj_exists returns False for a name it does not know AND for a query it
#could not make -- a read timeout looks identical to a bad name, so retry before
#believing it.
NED_ATTEMPTS = 3
NED_RETRY_SECONDS = 5


class SelectionError(Exception):
  """No usable observation for a source. Carries its own reason."""


@dataclass
class Target:
  """One thing a sweep was asked to image: a source, optionally held to projects."""
  name: str
  projects: list = field(default_factory=list)

  @property
  def label(self) -> str:
    return self.name + (f" ({', '.join(self.projects)})" if self.projects else '')

  def to_dict(self):
    return asdict(self)


def parse_target(text):
  """'3C 15' or '3C 15, AB0534' -> Target; a blank or '#' comment line -> None.

  Source names carry spaces and '+', never commas, so a comma is what splits the
  name from the project code(s) that follow it.
  """
  text = text.split('#', 1)[0].strip()
  if not text:
    return None
  name, *projects = [part.strip() for part in text.split(',')]
  if not name:
    raise ValueError(f"no source name in target {text!r}")
  return Target(name, [p.upper() for p in projects if p])


def read_targets(path):
  """Every target in a file, one per line (names.txt already fits)."""
  return [t for t in (parse_target(line) for line in
                      Path(path).read_text().splitlines()) if t]


@dataclass
class Selection:
  """One source's chosen observation and the archive files it needs."""
  name: str                 #the name as the user listed it
  alias: str = ''           #NED's own name for it, for SIMBAD/NED lookups
  archive_name: str = ''    #the Name column of the chosen row: the archive's own
  proj_code: str = ''
  segment: str = ''
  band: str = ''
  date: str = ''
  config: str = ''
  sensitivity: str = ''     #as reported, unit attached
  sensitivity_jy: float | None = None
  separation: str = ''      #pointing offset from the source, as reported (e.g. '0.7"')
  ra: str = ''
  decl: str = ''
  redshift: str = ''
  #the segment's archive files as {'name', 'date', 'size_mb'}. The date is kept per file,
  #not taken from the observation row, because it is what DelosDownload reads to
  #pick the Delos year directory -- and a segment can straddle a year boundary.
  files: list = field(default_factory=list)
  archive_files: list = field(default_factory=list)  #local paths, set by download()

  @property
  def file_names(self) -> list:
    return [f['name'] for f in self.files]

  @property
  def label(self) -> str:
    """'AM0221 seg B C-band' -- which observation of the source this is."""
    return f"{self.proj_code} seg {self.segment} {self.band}-band"

  @property
  def total_mb(self) -> float:
    return sum(f.get('size_mb') or 0.0 for f in self.files)

  @property
  def slug(self) -> str:
    """Filesystem-safe stem identifying this run, e.g. '3C_15__AM0221_B_C'.

    Segment and band are both in it: one source has many observations, and one
    segment can hold several bands.
    """
    safe = re.sub(r'[^A-Za-z0-9.+-]+', '_', self.name).strip('_') or 'source'
    return (f"{safe}__{self.proj_code or 'noproj'}_{self.segment or 'noseg'}_"
            f"{self.band or 'noband'}")

  def to_dict(self):
    return asdict(self)

  @classmethod
  def from_dict(cls, data):
    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def normalize_band(band):
  """A radio_search2 band code as the pipeline's band tables spell it, or None
  when the pipeline has no entry for it."""
  code = BAND_ALIASES.get(str(band).strip(), str(band).strip())
  return code if code in BAND_GHZ_RANGES else None


def parse_separation_arcsec(text):
  """radio_search2's Separation column in arcseconds, or None when unreadable.

  The column is written '0.7"', with the arcminutes appended once it is large
  ('91.7" (1.5\')'); the leading value is the one read. An arcminute (') or a bare
  number (taken as arcseconds) is accepted too. Anything else is None, never a guess.
  """
  match = re.fullmatch(r'\s*([0-9]*\.?[0-9]+)\s*("|\'|)\s*(\(.*\))?\s*', str(text or ''))
  if not match:
    return None
  value = float(match.group(1))
  return value * 60 if match.group(2) == "'" else value


def observation_date(selection):
  """A selection's observing date as a datetime, for putting epochs in order.

  Same two formats CLI._observation_year reads ('90-May-25', '1990-...'), and the
  same 2-digit pivot, which is strptime's own. Unreadable sorts last.
  """
  for fmt in ('%y-%b-%d', '%Y-%b-%d', '%Y-%m-%d'):
    try:
      return datetime.strptime(str(selection.date).strip(), fmt)
    except ValueError:
      continue
  return datetime.max


def within_size(selections, max_gb):
  """(kept, rejected): drop selections whose archive files exceed max_gb (0 = no cap)."""
  if not max_gb:
    return list(selections), []
  kept, rejected = [], []
  for selection in selections:
    if selection.total_mb / 1024 > max_gb:
      rejected.append((selection.label, f"{selection.total_mb / 1024:.1f} GB of archive "
                                        f"files is over max_gb {max_gb:g}"))
    else:
      kept.append(selection)
  return kept, rejected


def is_pre_evla(observation, before_year=PRE_EVLA_YEAR):
  """True when the observation predates the EVLA transition.

  Reuses CLI._observation_year, which already knows radio_search2's two date
  formats and the 2-digit pivot. An unreadable date is not pre-EVLA: the whole
  point of the filter is that the run is classic-VLA data, and a guess is not
  worth an unimportable archive halfway through a sweep.
  """
  year = CLI._observation_year(getattr(observation, 'date', ''))
  return year is not None and year < before_year


def rank_candidates(observations, before_year=PRE_EVLA_YEAR, projects=None, bands=None):
  """The pre-EVLA observations worth running, deepest first, one per run.

  parseObservations already returns the rows sorted by sensitivity ascending, so
  this filters and de-duplicates without reordering. A run is one (project,
  segment, band): radio_search2 can list the same one more than once (one row
  per IF or field name), and only the first -- the deepest -- is kept.

  `projects` / `bands`, when given, are sets of upper-case codes to keep.
  """
  candidates, seen = [], set()
  for obs in observations:
    if not is_pre_evla(obs, before_year):
      continue
    band = normalize_band(obs.band)
    if band is None:
      continue   #no spw range / cell size for this band; the run could not be sized
    if projects and obs.proj_code.upper() not in projects:
      continue
    if bands and band.upper() not in bands:
      continue
    key = (obs.proj_code, obs.seg, band)
    if key in seen:
      continue
    seen.add(key)
    candidates.append(obs)
  return candidates


class Selector:
  """Chooses a source's observations over one radio_search2 session."""

  def __init__(self, before_year=PRE_EVLA_YEAR, log=print):
    self.before_year = before_year
    self.log = log
    self._rs = None
    self._archfiles = {}   #proj_code -> [nrao_segment]; a project is asked about once

  def __enter__(self):
    self._rs = RadioSearchIntegration.connect()
    self._rs.__enter__()
    return self

  def __exit__(self, *exc):
    if self._rs is not None:
      self._rs.__exit__(*exc)
      self._rs = None

  def _resolve(self, source_name):
    """NED's record for a source, retried before it is called unresolvable."""
    for attempt in range(1, NED_ATTEMPTS + 1):
      if resolved := NED_API.obj_exists(source_name):
        return resolved
      if attempt < NED_ATTEMPTS:
        self.log(f"  NED gave nothing for '{source_name}' "
                 f"(attempt {attempt}/{NED_ATTEMPTS}); retrying")
        time.sleep(NED_RETRY_SECONDS)
    raise SelectionError(
      f"NED returned nothing for '{source_name}' in {NED_ATTEMPTS} attempts "
      f"(the name is unknown, or NED was unreachable -- its own message is above)")

  def segments_for(self, proj_code):
    """--archfileinfo for a project, parsed and cached for the session."""
    if proj_code not in self._archfiles:
      self._archfiles[proj_code] = parseArchFileInfo(self._rs('--archfileinfo', proj_code))
    return self._archfiles[proj_code]

  def select_all(self, source_name, projects=None, bands=None, max_sep_arcsec=None):
    """Every runnable pre-EVLA observation of `source_name`, deepest first.

    `max_sep_arcsec` keeps only observations pointed within that many arcseconds
    of the source; a row whose separation cannot be read is dropped with it.

    Returns (selections, rejected): rejected is [(label, reason)] for
    observations that passed the filters but cannot be run -- a segment that
    lists no archive files. Raises SelectionError when the source itself is a
    dead end: an unresolvable name, no archive data, nothing before the cutoff,
    or nothing in the requested projects/bands.
    """
    resolved = self._resolve(source_name)
    projects = {p.upper() for p in projects or ()}
    bands = {(normalize_band(b) or b).upper() for b in bands or ()}

    options = Options()
    options.search_alias = resolved['alias']
    options.band = 'auto'          #search every band; --bands filters afterwards
    observations = RadioSearchIntegration.run_search(self._rs, options)
    if not observations:
      raise SelectionError(f"radio_search found no observations for '{resolved['alias']}'")

    if missing := projects - {o.proj_code.upper() for o in observations}:
      self.log(f"  !! no observations of '{resolved['alias']}' in project(s): "
               f"{', '.join(sorted(missing))}")

    if max_sep_arcsec is not None:
      observations = self._near(observations, max_sep_arcsec)

    candidates = rank_candidates(observations, self.before_year, projects, bands)
    if not candidates:
      scope = ''.join([f" in {', '.join(sorted(projects))}" if projects else '',
                       f" at {', '.join(sorted(bands))}-band" if bands else '',
                       f' within {max_sep_arcsec:g}"' if max_sep_arcsec is not None else ''])
      raise SelectionError(
        f"no pre-{self.before_year} observation with a usable band{scope} "
        f"among {len(observations)} rows for '{resolved['alias']}'")

    selections, rejected = [], []
    for obs in candidates:
      #select_segment_files prints every file name, which for a catch-all segment
      #is thousands of them; the harness prints its own table instead
      with contextlib.redirect_stdout(io.StringIO()):
        files = RadioSearchIntegration.select_segment_files(
          self.segments_for(obs.proj_code), obs)
      if files:
        selections.append(self._build(source_name, resolved, obs, files))
      else:
        rejected.append((f"{obs.proj_code} seg {obs.seg} {obs.band}-band",
                         'the archive segment lists no files'))
    return selections, rejected

  def _near(self, observations, max_sep_arcsec):
    """The observations pointed within max_sep_arcsec of the source."""
    near, far, unreadable = [], 0, 0
    for obs in observations:
      sep = parse_separation_arcsec(getattr(obs, 'separation', ''))
      if sep is None:
        unreadable += 1
      elif sep > max_sep_arcsec:
        far += 1
      else:
        near.append(obs)
    if far or unreadable:
      self.log(f'  -- {far} row(s) further than {max_sep_arcsec:g}" from the source'
               + (f", {unreadable} with an unreadable separation" if unreadable else '')
               + ' dropped')
    return near

  @staticmethod
  def _build(source_name, resolved, obs, files) -> Selection:
    return Selection(
      name=source_name,
      alias=resolved['alias'],
      archive_name=obs.name,
      proj_code=obs.proj_code,
      segment=obs.seg,
      band=normalize_band(obs.band) or obs.band,
      date=obs.date,
      config=obs.cfg,
      sensitivity=obs.sensitivity,
      sensitivity_jy=sensitivity_jy(obs),
      separation=str(getattr(obs, 'separation', '') or '').strip(),
      ra=str(resolved['ra_decl']['ra']),
      decl=str(resolved['ra_decl']['decl']),
      redshift=str(resolved.get('redshift', '') or ''),
      files=[{'name': f.file_name, 'date': f.date, 'size_mb': size_mb(f)}
             for f in files],
      #the local paths DelosDownload will write to, derived from the same entries
      archive_files=[str(_local_path(obs.proj_code, f)) for f in files],
    )


def _local_path(proj_code, archfile):
  """Where DelosDownload will put one archive file: <repo>/data_archive/<proj>/<name>."""
  probe = Options()
  probe.proj_code = proj_code
  return DelosDownload([], probe).local_dir / Path(archfile.file_name).name


def download(selection: Selection, log=print, force=False):
  """Fetch the selection's archive files from Delos, skipping ones already held.

  Downloads are shared (data_archive/<proj_code>/), so a segment serving two
  bands is fetched once, and re-running re-fetches nothing. Only the missing files are asked for -- a segment is often several
  hundred megabytes per file, and one absent file should not re-pull the rest.
  """
  expected = [Path(p) for p in selection.archive_files]
  if not expected:
    raise SelectionError(f"{selection.name}: the chosen segment has no archive files")

  held = {p for p in expected if p.is_file() and p.stat().st_size}
  wanted = [f for f, path in zip(selection.files, expected) if path not in held]
  if not wanted and not force:
    log(f"  {len(expected)} archive file(s) already in {expected[0].parent}")
    return selection.archive_files

  options = Options()
  options.proj_code = selection.proj_code
  #rebuild the entries DelosDownload reads: it needs each file's own date to
  #build its Delos year directory, which the local paths alone do not carry
  entries = [_Entry(f['name'], f.get('date') or selection.date)
             for f in (selection.files if force else wanted)]
  log(f"  downloading {len(entries)} of {len(expected)} archive file(s)")
  DelosDownload(entries, options, verbose=True).download()

  #archive_files stays the full expected segment, not just what this call fetched
  absent = [str(p) for p in expected if not (p.is_file() and p.stat().st_size)]
  if absent:
    raise SelectionError(
      f"{selection.name}: archive file(s) missing after download: {', '.join(absent)}")
  return selection.archive_files


class _Entry:
  """The minimal shape DelosDownload reads off an archive-file entry."""
  def __init__(self, file_name, date):
    self.file_name = file_name
    self.date = date


def write_manifest(selections, path):
  """Persist the selection phase so the pipeline phase can be replayed."""
  path = Path(path)
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps([s.to_dict() for s in selections], indent=2) + '\n')
  return path


def read_manifest(path):
  return [Selection.from_dict(d) for d in json.loads(Path(path).read_text())]
