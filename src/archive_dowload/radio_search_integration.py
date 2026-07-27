#for doing a RADIO_SEARCH based Download
from classes.CLI_input import CLI
from classes.constants import DATA_ARCHIVE, FOLDER_NAME
from pre_calibration.options_class import Options
import json
import os
import pprint
import re
import subprocess
import paramiko
import getpass
from pathlib import Path
from typing import Optional, cast

CREDS_FILE = 'nraoCreds.json' #JSON creds next to this module: host/user/password/delos_url


def load_nrao_creds(required=('host', 'user', 'password')):
    """Load JSON credentials from nraoCreds.json (host/user/password/delos_url).

    `required` lists the keys that must be present and non-empty; raises otherwise.
    """
    creds_path = Path(__file__).resolve().with_name(CREDS_FILE)
    if not creds_path.exists():
        raise FileNotFoundError(f"Credentials file not found: {creds_path}")
    try:
        with open(creds_path, 'r') as creds_file:
            creds = json.load(creds_file)
    except json.JSONDecodeError as err:
        raise ValueError(f"Credentials file {creds_path} is not valid JSON: {err}")
    for key in required:
        if not creds.get(key):
            raise ValueError(f"Missing or empty '{key}' in credentials file {creds_path}.")
    return creds


class nrao_observeration:
    """
    Class to handle NRAO observations.
    """
    FIELDS = ['date', 'proj_code', 'seg', 'band', 'cfg', 'resln',
               'las', 'frequency', 'bandwidth', 'time', 'nants',
               'sensitivity', 'nscans_hours', 'separation', 'name']

    #attributes set dynamically from FIELDS in __init__; declared here so the
    #type checker knows them (all parsed as strings from the radio_search2 table)
    date: str
    proj_code: str
    seg: str
    band: str
    cfg: str
    resln: str
    las: str
    frequency: str
    bandwidth: str
    time: str
    nants: str
    sensitivity: str
    nscans_hours: str
    separation: str
    name: str

    def __init__(self, fields):
        #Date      |ProjCode  |Seg    |Band |Cfg |Resln	|LAS	|Frequency	|Bandwidth	|Time	|NAnts	|Sensitivity	|Nscans/Hours	|Separation	|Name
        for attr, value in zip(self.FIELDS, fields):
            setattr(self, attr, value)

    def __repr__(self):
        return f"{self.__dict__}"


class nrao_archfile:
    """
    Class to represent a single archive file entry from --archfileinfo output.
    """
    def __init__(self, file_number, file_name, band, date, start, size):
        self.file_number = file_number
        self.file_name = file_name
        self.band = band
        self.date = date
        self.start = start
        self.size = size

    def __repr__(self):
        return f"{self.__dict__}"


class nrao_segment:
    """
    Class to represent a segment from --archfileinfo output.
    Contains a segment name and a list of nrao_archfile objects.
    """
    def __init__(self, name, files):
        self.name = name
        self.files = files

    def __repr__(self):
        return f"Segment {self.name}: {self.files}"


class RadioSearch2:
    """
    Persistent SSH connection for multiple radio_search2 calls.
    
    Usage:
        with RadioSearch2() as rs:
            result1 = rs('4C35.03', 'BANDS', 'C')
            result2 = rs('--archfileinfo', '13B-326') #second is project code 
            result3 = rs('3C273', 'BANDS', 'X', 'CONF', 'A')
    """
    def __init__(self, host, user, password=None, key_filename=None, remote_path=None):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.remote_path = remote_path #radio_search2 dir on the host; from nraoCreds.json

        connect_kwargs = {"hostname": host, "username": user}
        if key_filename:
            connect_kwargs["key_filename"] = key_filename
        elif password:
            connect_kwargs["password"] = password
        else:
            connect_kwargs["password"] = getpass.getpass(f"{user}@{host} password: ")
        
        self.client.connect(**connect_kwargs)
    
    def __call__(self, *args):
        quoted_args = " ".join(f"'{a}'" for a in args)
        remote_cmd = (
            f"cd {self.remote_path} "
            f"&& ./radio_search2 {quoted_args}"
        )
        
        stdin, stdout, stderr = self.client.exec_command(remote_cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        
        if err:
            print(f"radio_search2 stderr:\n{err}")
        
        return out
    
    def __enter__(self):
        return self
    
    def __exit__(self, *exc):
        self.client.close()


def parseArchFileInfo(results):
    """
    Parse the output of radio_search2 --archfileinfo into a list of nrao_segment objects.
    """
    segments = []
    current_segment_name = None
    current_files = []

    for line in results.splitlines():
        seg_match = re.match(r'^Segment\s+(\S+)', line)
        if seg_match:
            if current_segment_name is not None:
                segments.append(nrao_segment(current_segment_name, current_files))
            current_segment_name = seg_match.group(1)
            current_files = []
            continue
        if line.startswith('---') or not line.strip():
            continue
        if '#' in line and 'File' in line and 'Start' in line:
            continue
        parts = line.split()
        #data rows begin with a numeric file number; skip headers/footers
        if not parts or not parts[0].isdigit():
            continue
        # columns: file_number, file_name, band, date, time(start), size
        # radio_search2 can emit short rows (a trailing "N files" summary line, or
        # a file row missing its time/size columns) that still start with a digit.
        # Guard the positional access so one short line doesn't abort the whole
        # import; only file_name and date are actually used downstream.
        if len(parts) < 4:
            continue  #not a real file row (file_number, file_name, band, date min)
        file_number = int(parts[0])
        file_name = parts[1]
        band = parts[2]
        date = parts[3]
        start = parts[4] if len(parts) > 4 else ''
        size = parts[5] if len(parts) > 5 else ''
        current_files.append(nrao_archfile(file_number, file_name, band, date, start, size))

    if current_segment_name is not None:
        segments.append(nrao_segment(current_segment_name, current_files))

    return segments


def parseObservations(results):
    """
    Parse the output of radio_search2 into a list of nrao_observeration objects.
    """
    observations = []
    separator_count = 0
    in_data = False
    for line in results.splitlines():
        if line.startswith('---'):
            separator_count += 1
            if separator_count >= 2:
                in_data = True
            continue
        if not in_data or not line.strip():
            continue
        if line.strip().lower() == 'done.':
            break
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 15:
            continue
        if parts[0].lower() == 'date':
            continue
        if parts[1].upper() == 'SYSTEM':
            continue
        observations.append(nrao_observeration(parts[:15]))
    return observations



class RadioSearchIntegration:
  """Class to handle integration of radio_search into the HVLA Image Machine workflow."""

  @staticmethod
  def perform_radio_search(options:Options):
    """Perform the radio search and download archives based on user input."""
    # This is a placeholder for the actual implementation of the radio search.
    # You would need to implement the logic to interact with the radio search tool,
    # process the results, and download the relevant archives.
    CLI.getSourceInfo(options)
    #DO radio_search with options.source and options.band

    creds = load_nrao_creds(required=('host', 'user', 'password', 'radio_search_path'))
    with RadioSearch2(host=creds['host'], user=creds['user'], password=creds['password'],
                      remote_path=creds['radio_search_path']) as rs:
        #'auto' (or empty) means "all bands": radio_search2 wants NO 'BANDS' keyword
        #in that case. Passing 'BANDS auto' makes the wrapper look up a non-existent
        #band, drop the (empty) bandno token, and shift a config-group string into the
        #int bandno slot -> "invalid literal for int()". Only pass BANDS for a real band.
        if options.band and options.band != 'auto':
            rs_results = rs(options.search_alias, 'BANDS', options.band)
        else:
            rs_results = rs(options.search_alias)
        #process unformatted RS return, get user input
        observations = parseObservations(rs_results)

        #selectObservation returns one of the nrao_observeration objects we passed in (or None)
        selected_obs = cast(Optional[nrao_observeration], CLI.selectObservation(observations))
        if selected_obs is None:
            print("No observation selected.")
            return
        print(f"\nSelected: {selected_obs.proj_code}  segment {selected_obs.seg}  ({selected_obs.date})")

        raw_archfileinfo = rs('--archfileinfo', selected_obs.proj_code)
        #capture the raw output so the actual column layout is inspectable when a
        #row fails to parse (the print previously claimed this without writing it).
        archfiles_file = Path(__file__).resolve().parent / 'archfiles.txt'
        archfiles_file.write_text(raw_archfileinfo)
        print(f"Archive file info written to {archfiles_file}")
        archfiles = parseArchFileInfo(raw_archfileinfo)

        options.proj_code = selected_obs.proj_code
        #return the file(s) to download to the caller (radio_search), which will
        #hand them to DelosDownload on a separate thread.
        return RadioSearchIntegration.select_segment_files(archfiles, selected_obs)

  @staticmethod
  def select_segment_files(archfiles, selected_obs):
    """Select the archive file(s) belonging to the selected observation's segment.

    Returns the list of nrao_archfile objects to be downloaded from the NAS
    (the actual download is handled by DelosDownload). The full objects are kept
    so DelosDownload can read each file's observation date -> Delos year directory.

    archfiles: list of nrao_segment objects (from parseArchFileInfo).
    selected_obs: the nrao_observeration chosen by the user.
    """
    selected_segment = next(
        (seg for seg in archfiles if seg.name == selected_obs.seg), None
    )
    if selected_segment is None:
        print(f"No archive files found for segment {selected_obs.seg}.")
        return []

    download_files = selected_segment.files
    print(f"Files to download for segment {selected_obs.seg}: "
          f"{[archfile.file_name for archfile in download_files]}")
    return download_files


class DelosDownload:
    """Downloads the selected archive files from the Delos NAS over HTTP (curl).

    The Delos 'oldstyle' archive is laid out by observation year:
        {base_url}{year}/{file_name}
    e.g. 

    The base URL is read from nraoCreds.json ('delos_url' key). The 4-digit year is taken
    from each file's --archfileinfo entry (its observation date, falling back to the
    YY embedded in the file name).

    Files are saved under <repo>/data_archive/<proj_code>/ and the resulting local
    paths are written to options.archive_files for do_vla_import/importvla.

    Designed to run on its own thread while CLI calibration info is gathered in parallel.
    """

    #curl: fail on HTTP errors, show errors, retry, create parent dirs, bounded timeouts
    CURL_BASE = ['curl', '-fsS', '--retry', '3', '--create-dirs',
                 '--connect-timeout', '30', '--max-time', '600']

    #curl exit codes that mean "couldn't establish a connection at all" (as opposed
    #to an HTTP error like 403/404). Used by the reachability pre-check to tell a
    #dead/unreachable host apart from one that answered with an error status.
    #6=DNS, 7=connection refused, 28=connect timeout, 35=TLS connect error.
    CONNECT_FAIL_CODES = {6, 7, 28, 35}

    def __init__(self, download_files, options, local_dir=None, base_url=None, verbose=False):
        self.download_files = download_files or []
        self.options = options
        self.base_url = base_url
        #quiet by default: this runs on a worker thread alongside the interactive
        #calibration prompts, so per-file prints would interleave with input().
        self.verbose = verbose
        self.error = None #set by run() if download() raises, for the caller to inspect after join
        self.local_dir = Path(local_dir) if local_dir else self._default_local_dir()

    def _default_local_dir(self):
        """<repo_root>/data_archive/<proj_code>/ , built from constants."""
        proj = self.options.proj_code or 'unknown_project'
        return self._repo_root() / DATA_ARCHIVE.strip('/') / proj

    @staticmethod
    def _repo_root():
        """Locate the hvla_image_machine project root from this file's path."""
        here = Path(__file__).resolve()
        for parent in here.parents:
            if parent.name == FOLDER_NAME:
                return parent
        return here.parents[2] #<root>/src/archive_dowload/<file> -> <root>

    def _resolve_base_url(self):
        """Delos archive base URL (constructor override or nraoCreds.json), trailing '/'."""
        url = self.base_url or load_nrao_creds(required=('delos_url',))['delos_url']
        return url if url.endswith('/') else url + '/'

    @staticmethod
    def _file_name(entry):
        """An entry may be an nrao_archfile or a bare file-name string."""
        return getattr(entry, 'file_name', entry)

    @classmethod
    def _archive_year(cls, entry):
        """4-digit observation year for an entry. Uses the date field first, then a
        year embedded in the file name. Handles both the old 2-digit form (e.g.
        '87-Aug-20' / VLA_XH87021...) and the newer 4-digit form (e.g. '2003-11-17'
        / vla2003-11-17.dat)."""
        date = getattr(entry, 'date', None)
        if date:
            year = cls._normalize_year(str(date).split('-')[0])
            if year:
                return year
        name = str(cls._file_name(entry))
        #prefer a full 4-digit year in the name, else fall back to a 2-digit year
        match = re.search(r'(?:19|20)\d{2}', name) or re.search(r'\d{2}', name)
        year = cls._normalize_year(match.group(0)) if match else None
        if not year:
            raise ValueError(f"Cannot determine observation year for {entry!r}")
        return year

    @staticmethod
    def _normalize_year(token):
        """Normalize a year token to a 4-digit year string: 4-digit (1900-2099) as-is;
        2-digit via pivot 69 (69-99 -> 19xx, else 20xx). None if not a year."""
        token = str(token).strip()
        if not token.isdigit():
            return None
        if len(token) == 4 and 1900 <= int(token) <= 2099:
            return token
        if len(token) == 2:
            n = int(token)
            return str(1900 + n if n >= 69 else 2000 + n)
        return None

    def remote_url(self, entry, base_url=None):
        """Build the Delos HTTP URL for an archive file entry. The file name may be a
        bare name (VLA_XH87021_file2.dat) or carry a subpath (VLA/2003-11/vla2003-11-17.dat);
        Delos stores everything by year as {base}{year}/{basename}."""
        base = base_url or self._resolve_base_url()
        return f"{base}{self._archive_year(entry)}/{Path(self._file_name(entry)).name}"

    def run(self):
        """Thread entry point: run download(), capturing any exception so the caller
        can surface it after join() (exceptions raised in a worker thread are
        otherwise lost). download() itself still raises for direct/programmatic use.
        """
        try:
            self.download()
        except Exception as exc:
            self.error = exc

    def _check_reachable(self, base_url):
        """Pre-poke the Delos host before downloading anything.

        Without this, an offline/unreachable Delos makes every per-file curl burn
        --connect-timeout * (--retry + 1) seconds of silent retries in a row, which
        looks like a hang (this runs on a worker thread with verbose=False while the
        CLI prompts run in parallel). A single short probe up front lets us fail fast
        with a clear message instead.

        We deliberately do NOT pass -f here: an HTTP error (e.g. 403 on a directory
        with listing disabled) still proves the host is up and answering, so only a
        connection-level failure (CONNECT_FAIL_CODES) counts as unreachable.
        """
        probe = subprocess.run(
            ['curl', '-sS', '-o', os.devnull, '--head',
             '--connect-timeout', '10', '--max-time', '15', base_url],
            capture_output=True, text=True,
        )
        if probe.returncode in self.CONNECT_FAIL_CODES:
            raise RuntimeError(
                f"Delos NAS is not reachable at {base_url} (curl exit {probe.returncode}: "
                f"{probe.stderr.strip() or 'connection failed'}).\n"
                f"The host may be offline, or this machine may not be on the "
                f"NRAO/UMBC network / VPN. Aborting before download."
            )

    def download(self):
        """Fetch each archive file from Delos into local_dir; record the local paths."""
        base_url = self._resolve_base_url()
        self._check_reachable(base_url)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        local_paths = []
        for entry in self.download_files:
            url = self.remote_url(entry, base_url)
            local_path = self.local_dir / Path(self._file_name(entry)).name
            self._curl(url, local_path)
            local_paths.append(str(local_path))
        #do_vla_import/importvla needs the local paths it can open
        self.options.archive_files = local_paths
        return local_paths

    def _curl(self, url, local_path):
        """Download one file with curl; raise on failure or empty result."""
        if self.verbose:
            print(f"Downloading {url} -> {local_path}")
        result = subprocess.run(
            self.CURL_BASE + ['-o', str(local_path), url],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"curl failed ({result.returncode}) for {url}\n{result.stderr.strip()}"
            )
        if not local_path.exists() or local_path.stat().st_size == 0:
            raise RuntimeError(f"Download produced no data: {local_path}")
        return local_path
