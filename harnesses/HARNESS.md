# Harnesses

Run the pipeline over many observations, unattended and in parallel. Each run
gets its own working directory and its own results folder. A run that fails is
recorded in the sweep's oversight log and does not stop the runs beside it.

```bash
bash tools/run_harness.sh full-auto "3C 15" "3C 31, AL0405"              # deepest obs of each
bash tools/run_harness.sh full-auto --targets-file names.txt --preset full_auto_selfcal
bash tools/run_harness.sh lightcurve "4C 35.03" --bands C                # every epoch < 100"
bash tools/run_harness.sh lightcurve "4C 35.03" --preset lightcurve_deep # interactive, attended
bash tools/run_harness.sh full-auto --targets-file names.txt --select-only   # search + download only
bash tools/run_harness.sh resume harnesses/sweeps/full-auto_full_auto_20260924-150000  # re-run what didn't pass
bash tools/run_harness.sh summarize harnesses/sweeps/lightcurve_lightcurve_20260924-161811  # re-plot a lightcurve
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

## Lightcurves

After every pass, and again after each `resume`, the `lightcurve` harness collects
the 2D Gaussian fit the pipeline makes of each passed run's final image
(`<name>.fit.json` in its results folder) and writes, into the sweep folder:

- `lightcurve.csv`: one row per passed run with a fit, oldest first. Includes the
  integrated and peak flux density with their errors, frequency, observing time
  (ISO and MJD), primary-beam response, pointing separation, array config and beam.
- `lightcurve_<source>.png`: integrated and peak flux density against time, one row
  of panels per band.

Each time is the middle of the target's observing span, from the results folder's
listobs. When that listobs is missing, the archive date is used instead.

The pipeline fits the flat-noise image, which is not corrected for the primary
beam. That attenuates a source pointed off-centre, and this harness takes pointings
up to `max_sep_arcsec` away. So every flux and error is divided by the primary-beam
response at the fitted peak, read from `<name>.fits` and `<name>.pbcor.tt0`.

An epoch is listed in the CSV but left off the plot when:

- the fit did not converge
- there is no primary-beam response to correct it with
- it has no observing time

The CSV's `note` column says which. Error bars are imfit's statistical errors only,
with no flux-scale term.

`summarize <sweep folder>` rebuilds both files from whatever has passed so far,
including for a sweep made before this existed.

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
`cleanup` and `attended`. `full-auto` also takes `all_obs`, and `lightcurve` takes
`max_sep_arcsec`. The flag for each one is the same name with dashes, e.g.
`--batch-size`, except `--no-cleanup` and `--max-sep`.

**`seed`** sets any `import.json` key except the ones that describe the
observation (`source`, `archive_file(s)`, `band`, `proj_code`, NED fields). Those
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
| `lightcurve`        | fixed imaging (size, cell, weighting) so epochs can be compared; parallel |
| `lightcurve_deep`   | as `lightcurve`, cleaned interactively; attended |

The lightcurve presets use a fixed `cell_size` of `0.08arcsec`, which suits
X-band A-config. Set it for your band and array, and pass `--bands` so every
epoch really is comparable.

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

1. NED resolves the name.
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

The `runs/`, `failed_tests/`, `manifest.json` and `harness_report.json` left in
this folder are from the old `auto_harness.py` and aren't used any more. Delete
them when you no longer need them.

## Exit status

`0` when everything selected passed, `1` when anything failed or couldn't be
selected, `2` on a bad invocation or preset, `130` on interrupt.
