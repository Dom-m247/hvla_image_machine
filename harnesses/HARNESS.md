# Harnesses

Run the pipeline over many observations, unattended and in parallel. Each run
gets its own working directory and its own results folder. A run that fails is
recorded in the sweep's oversight log and does not stop the runs beside it.

```bash
bash tools/run_harness.sh full-auto "3C 15" "3C 31, AL0405"              # deepest obs of each
bash tools/run_harness.sh full-auto --targets-file names.txt --preset full_auto_selfcal
bash tools/run_harness.sh lightcurve "4C 35.03" --bands C                # every epoch < 100"
bash tools/run_harness.sh lightcurve "4C 35.03" --bands C --sigma 3      # detect down to 3 sigma
bash tools/run_harness.sh lightcurve "4C 35.03" --preset lightcurve_deep # interactive, attended
bash tools/run_harness.sh full-auto --targets-file names.txt --select-only   # search + download only
bash tools/run_harness.sh resume harnesses/sweeps/full-auto_full_auto_20260924-150000  # re-run what didn't pass
bash tools/run_harness.sh summarize harnesses/sweeps/lightcurve_lightcurve_20260924-161811  # re-plot a lightcurve
bash tools/run_harness.sh summarize harnesses/sweeps/lightcurve_lightcurve_20260924-161811 --sigma 3  # ...at 3 sigma
bash tools/run_harness.sh presets                                        # list presets
```

## Running it

`tools/run_harness.sh` is the way in. It works from any directory and runs
`harnesses/run_harness.py` with the pipeline's own interpreter (`.hvla_env`),
which the harness needs because it imports the pipeline's modules, and those need
CASA. Arguments pass through unchanged.

- Relative paths (`--targets-file`, a resume folder) are read from your current
  directory. Sweeps are written to `harnesses/sweeps/` unless you pass `--sweeps-dir`.
- When `HVLA_CPU_CORES` (the variable `run.sh` pins to) is set, it becomes
  `--cores` for a sweep that doesn't pass its own. `export` it in your shell rc to
  pin every sweep. The `hvla_image` function from `install_alias.sh` only sets it
  while it calls `run.sh`.
- If `.hvla_env` doesn't exist yet, it stops and tells you to run `./run.sh` once.
- CASA writes a `casa-*.log` into the directory you start the sweep from.

Calling it directly is the same thing:
`.hvla_env/bin/python harnesses/run_harness.py ...`.

## Harnesses

| harness      | runs                                                            | default preset |
|--------------|-----------------------------------------------------------------|----------------|
| `full-auto`  | the most sensitive observation of each target (`--all-obs` for every one) | `full_auto` |
| `lightcurve` | every observation pointed within `max_sep_arcsec` (100") of each target, oldest first | `lightcurve` |

Both keep only observations from before `before_year` (2009). The Delos download
only handles classic-VLA archive segments.

Both search the archive twice: on the target's J2000 coordinates, and on its B1950
coordinates (`EPOCH 1950`). The archive lists some early observations at positions
never transformed to J2000, and the J2000 search misses those outright or reports
them at the wrong separation (a 1983 A2218 pointing really 60" away comes back as
426"). A run both searches find keeps the row that puts it nearer the target; the
selection table marks one found on B1950 coordinates `(B1950)`.
`--no-b1950-search` skips the second search.

`--bands` is passed to the archive search itself, not only applied afterwards: an
all-band search takes minutes.

## How each epoch is imaged

Self-calibration has to model the field the observation was set up for: a faint target
can sit under the sidelobes of a field source a thousand times brighter, whatever the
exposure. So by default (`field_of_view: primary_beam`) every epoch is imaged properly,
whichever source you are after:

- The main image is centred on the **pointing**, in J2000, and is 1024 pixels across at
  a fifth of a beam per pixel (never wider than twice the primary-beam FWHM, which only
  matters in D configuration). Old data record positions as B1950_VLA, which CASA
  handles correctly but `exportfits` writes as `EQUINOX 1979.9`; imaging in J2000 avoids
  every other reader (DS9, astropy) putting the image ~20' from where it is.
- NVSS sources beyond the main image, out to twice the primary-beam FWHM, whose flux
  after the primary beam reaches 5 mJy get small **outlier fields**, cleaned jointly
  with the main image so they are in the self-cal model at their own positions (as AIPS
  SETFC/IMAGR facets do). So does the target, if it falls outside the main image (it is
  then measured there).
- A **residual sweep** catches what the catalogue misses (flat-spectrum sources at high
  frequency, sources that flared after NVSS, the sky south of -40 deg): the residual
  visibilities (data minus model) are imaged dirty over three primary-beam FWHMs at low,
  tapered resolution. After the initial clean, any peak outside every imaged field
  above 6 sigma (and above a fifth of the brightest residual inside them, so it is not
  a sidelobe) gets an outlier field and the initial clean is made again. The same sweep
  after the last cycle only warns; its image is saved as `<name>.sweep.png`.
- **W-projection** switches on when the field is wide enough for the sky's curvature to
  matter (most L-band fields, high-resolution wide fields).
- **Self-cal** is on in the lightcurve presets. Whether to try it is judged on the whole
  field's cleaned flux (at least 20 mJy), not the target's; each cycle is kept only if it
  raises the dynamic range.
- An epoch likely to be hard for a faint target is **warned about**, not skipped: a
  low-frequency band (4, P, L, S, C) with the target below half power in the beam, or a
  catalogued field source more than 1000 times the image noise.

The `lightcurve_fast` preset is the opt-out: for a bright, point-like target that is the
pointing target of every epoch chosen, a small fixed field and no self-cal.

## Where the target is measured

Every run measures the target at its catalogue position (SIMBAD, else NED; J2000), not wherever the
image happens to peak:

- The target is **detected** when the brightest pixel within one beam of its position
  reaches `detection_sigma` (default **5**) times the off-source rms. A 2D Gaussian is
  then fitted in a box around it.
- Otherwise the result is an **upper limit** of `detection_sigma` times the rms.
- A Gaussian is fitted whenever the peak reaches 3 sigma (`FIT_MIN_SNR`), so a sweep can
  be re-thresholded down to that without re-imaging.

`<name>.fit.json` records the target position, its separation from the pointing
centre (from the data, converted by CASA), the primary-beam response there, the
detection (peak, S/N, threshold, upper limit) and the fit, if any. It also records
the noise of a Stokes V image made like the others. Stokes I noise well above it means
the image is limited by dynamic range or calibration rather than noise. It is not the
thermal noise itself: bad data and short snapshots raise V as much as I.

Set the threshold with `--sigma` on a sweep, `detection_sigma` in a preset's seed, or
(for a single run) at the CLI prompt or in `import.json`.

## Lightcurves

After every pass, and again after each `resume`, the `lightcurve` harness collects
the measurement the pipeline makes of each passed run's final image
(`<name>.fit.json` in its results folder) and writes, into the sweep folder:

- `lightcurve.csv`: one row per passed run with a fit record, oldest first. Includes
  detection (S/N, threshold), the integrated and peak flux density with their errors
  or the upper limit, frequency, observing time (ISO and MJD), primary-beam response,
  the pointing separation from the data and from the archive, the image noise in
  Stokes I and V, array config and beam.
- `lightcurve_<source>.png`: integrated and peak flux density against time, one row
  of panels per band; detections as points, upper limits as open triangles.

Each time is the middle of the target's observing span, from the results folder's
listobs. When that listobs is missing, the archive date is used instead.

Measurements are made on the flat-noise image, which is not corrected for the primary
beam. That attenuates a source pointed off-centre, and this harness takes pointings
up to `max_sep_arcsec` away. So every flux, error and limit is divided by the
primary-beam response at the target.

An epoch is listed in the CSV but left off the plot when:

- the data put the pointing further than `max_sep_arcsec` from the target, whatever
  the archive said (an early observation found on B1950 coordinates can coincide by
  chance with a field that is really arcminutes away)
- the target is outside the image, or has no primary-beam response
- it has no observing time

The `note` column says which. It also notes a plotted epoch whose pointing separation
disagrees with the archive's by more than 10", and a detection whose Gaussian did not
converge or landed more than a beam from the target -- plotted from its peak pixel,
with no integrated flux. Error bars are imfit's statistical errors only, with no
flux-scale term.

An observation with no standard flux calibrator (3C286, 3C48, 3C147, 3C138) is not
dropped: its flux scale is set from the nearest calibrator's flux in the VLA
calibrator list, which may then serve as phase calibrator too. Calibrators vary, so
that scale is good to perhaps 10-20%. Such an epoch is flagged everywhere it appears:
a warning banner in the run, `*** CATALOGUE ***` in the run log, `flux_scale` in
`fit.json` and the CSV, and outlined marks on the plot.

`summarize <sweep folder>` rebuilds both files from whatever has passed so far, and
`summarize <sweep folder> --sigma N` re-decides every epoch at threshold N from the
recorded S/N, without re-imaging. A run made before target-based measurement is read
the old way, from the Gaussian at the image peak, and noted as such.

## Targets

A target is a source name, or `name, PROJ[, PROJ...]` to limit it to those
projects. Give them as arguments, or one per line in `--targets-file`, where `#`
starts a comment. The repo's `names.txt` is already in this format. A target that names
its own projects ignores `--projects`.

## Presets

A preset is a JSON file in `presets/`. Pick one with `--preset NAME`, or give a
path to a preset file somewhere else.

```jsonc
{
  "harness": "lightcurve",          // the harness it belongs to
  "label": "shown by the presets command",
  "options": { ... },               // harness settings; any flag overrides them
  "seed":    { ... }                // import.json settings every run is driven by
}
```

**`options`** can be `batch_size`, `cores`, `timeout`, `bands`, `projects`,
`before_year`, `max_gb`, `limit` (per target), `source_name` (`archive`|`input`),
`cleanup`, `attended`, `sigma` (detection threshold; overrides the seed's
`detection_sigma`) and `b1950_search`. `full-auto` also takes `all_obs`, and
`lightcurve` takes `max_sep_arcsec`. The flag for each one is the same name with
dashes, e.g. `--batch-size`, except `--no-cleanup`, `--no-b1950-search` and `--max-sep`.

**`seed`** sets any `import.json` key except the ones that describe the
observation (`source`, `archive_file(s)`, `band`, `proj_code`, catalogue fields). Those
always come from the selected observation. `decisions` is merged key by key into
the baseline (everything `auto`, with self-cal, blcal and core subtraction `off`),
so a preset only lists what it changes. The defaults are in `harness/seed.py`
(`recipe`).

Presets are checked when they load, before any network call. The sweep refuses
to start if a preset:

- sets an observation key
- has a key `import.json` doesn't have
- uses an invalid decision mode
- turns on `use_custom_cell_size` without a `cell_size`
- turns on self-cal without `self_cal_cycles`
- in an unattended preset, uses any decision mode other than `auto`/`off`/`force`,
  or sets `interactive_image`. The calibrator pickers prompt even under
  `--importRun`, and nobody would be there to answer.

| preset              | what it is |
|---------------------|------------|
| `full_auto`         | auto cal/flag/refant, one clean, no self-cal |
| `full_auto_selfcal` | as above, plus the scored self-cal ladder (4 cycles) |
| `lightcurve`        | each epoch's primary-beam field imaged and self-calibrated, target measured at its position (5 sigma); parallel |
| `lightcurve_deep`   | as `lightcurve`, cleaned interactively; attended |
| `lightcurve_fast`   | bright point target at the pointing centre of every epoch: small field, no self-cal |

The lightcurve presets leave the cell size to the pipeline: a tenth of the beam for
each epoch's band and array configuration. A fixed cell cannot suit both: an
archive's epochs span A to D configuration, and the 0.08" these presets once fixed
gave a 1024-pixel image only 82" across, smaller than the D-configuration L-band beam.
Pass `--bands` so every epoch really is comparable.

## Attended sweeps

A preset with `"attended": true` (`lightcurve_deep`) is for a person at the display:

- one run at a time
- `DISPLAY` kept, stdin left on the terminal
- no timeout
- output shown on the terminal and saved to `harness_run.out`

The sweep won't start without `DISPLAY`. Every observation is searched and
downloaded before the first run, so there is no waiting between runs. With no
saved mask, the pipeline asks for one at the start of each run; press enter to
clean interactively.

## A sweep's folder

```
sweeps/<harness>_<preset>_<YYYYmmdd-HHMMSS>/
  sweep.json        the preset (copied, not linked), options and targets
  manifest.json     the selected observations
  oversight.log     one line per event, written as it happens
  oversight.jsonl   the same events as JSON
  report.json       per-run status; updated by every pass, including resumes
  lightcurve.csv    lightcurve only: every passed epoch's fit (see Lightcurves)
  lightcurve_<source>.png  lightcurve only: flux density over time
  runs/<slug>/      a run's working directory, ending in its own *_results/
  failed/<slug>_failed/  what a failed run left behind
```

`<slug>` is `<source>__<proj>_<seg>_<band>`. Events are `sweep-start`,
`selected`, `skipped`, `run-start`, `run-end` (status, minutes, results folder),
`failure` (reason, artifact folder), `sweep-resume`, `summary-failed` and `sweep-end`.

**Resume** re-runs every run whose last `run-end` wasn't `passed`, using the
copied preset in `sweep.json` and reusing each run directory: importvla and the
splits skip work already on disk. `--fresh` wipes a run directory first.
`--batch-size`, `--cores`, `--timeout` and `--no-cleanup` can be changed when you
resume. A target that failed selection has no run to resume, so start a new
sweep for it.

## What counts as a pass

A zero exit status is not enough. The pipeline gets out of several dead ends
with a bare `sys.exit()`, which exits 0. A run passes only when it exited 0 **and**
produced a new `*_results/` folder.

| status        | meaning |
|---------------|---------|
| `passed`      | exited 0 and produced a results folder |
| `failed`      | exited non-zero |
| `no-results`  | exited 0 but imaged nothing |
| `timeout`     | killed at `timeout` |
| `setup-error` | never reached the pipeline (selection, download, seeding, a harness bug) |
| `skipped`     | `--dry-run` |

A failed run's `failed/<slug>_failed/` holds:

- `failure.txt` / `failure.json`
- `harness_run.out`, with the progress animation's redraws collapsed
- the CASA logs, `import.json`, `harness_seed.json`, `replay.py` and the listobs files
- any results folder, minus its tarballs

The run directory itself is left as it was, so you can inspect it.

## How a run is driven

The pipeline's `-rs` flag can't be automated, because it prompts for everything.
So the harness calls the same modules `-rs` uses:

1. SIMBAD resolves the name (NED if SIMBAD does not know it).
2. `RadioSearchIntegration.run_search` searches every band.
3. The harness filters and ranks the results.
4. `DelosDownload` fetches the segment into the shared `data_archive/<proj>/`.

It then writes an `import.json` and runs
`python src/HVLA_image_machine.py --importRun --no-ms-tar` in the run directory,
with stdin on `/dev/null` and no `DISPLAY` (except when attended). `--importRun`
makes every mid-run prompt resolve itself. The closed stdin means a prompt that
gets through fails that one run with `EOFError` instead of hanging the sweep.

A passed run gets the project's `cleanup.sh`, which deletes the measurement sets
and scratch and keeps `*_results/`, unless `--no-cleanup` is given.

## Layout

```
../tools/run_harness.sh  wrapper: the venv interpreter, HVLA_CPU_CORES -> --cores
run_harness.py        entry point: arguments, presets, targets
presets/*.json        the presets
harness/
  pipeline.py         the one place that imports src/
  presets.py          load, merge and validate presets
  kinds/              full_auto.py, lightcurve.py: which observations a target runs
  lightcurve_plot.py  the lightcurve harness's summary: fits -> CSV + plot
  selection.py        targets, name -> observations -> archive files, the manifest
  seed.py             the import.json a run is driven by
  sweep.py            sweep folder, oversight log, batches, report, resume
  runner.py           one run: its directory, its subprocess, its cleanup
  failures.py         failure artifacts
```

To add a harness, add a module to `harness/kinds/` with `NAME`, `HELP`,
`DEFAULT_PRESET`, `DEFAULT_OPTIONS` and `choose(selector, target, options)`,
register it in `kinds/__init__.py`, and add a preset for it. An optional
`summarize(sweep)` runs after every pass. It builds the sweep-wide products, and
a failure in it is logged without changing the sweep's exit status.

## Exit status

`0` when everything selected passed, `1` when anything failed or couldn't be
selected, `2` on a bad invocation or preset, `130` on interrupt.
