# HVLA Image Machine

**An automated calibration and imaging pipeline for archival VLA radio-interferometry data.**

The HVLA Image Machine takes a radio source by name and your raw observation
data, then drives the full [CASA](https://casa.nrao.edu/) workflow  with sensible defaults and the possibility of minimal manual intervention. It is designed to make reducing historical VLA observations
approachable through a guided GUI, a scriptable CLI, and fully reproducible calibration and imaging configurations.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Credentials](#credentials)
- [Configuration](#configuration)
- [Providing Observations](#providing-observations)
- [Usage](#usage)
- [Archiving and Submission](#archiving-and-submission)
- [Reproducible Runs](#reproducible-runs)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

Reducing radio-interferometry data by hand is a long, error-prone sequence of
CASA tasks: importing the archive, flagging, deriving flux/bandpass/gain
solutions, applying calibration, splitting the target, and iteratively cleaning.
The HVLA Image Machine wraps that sequence into a single, repeatable pipeline.

Given a source name and a local observation file, the tool:

1. **Resolves** the object against the [NED](https://ned.ipac.caltech.edu/) and
   [SIMBAD](https://simbad.u-strasbg.fr/simbad/) catalogs to confirm it exists
   and recover its coordinates.
2. **Imports** your raw VLA archive into a CASA measurement set and parses its
   `listobs` metadata.
3. **Calibrates** the measurement set (flux scaling with `setjy`, bandpass,
   gain, fluxscale bootstrapping, and applycal).
4. **Images** the calibrated target with `tclean`, with optional interactive
   cleaning and self-calibration cycles.
5. **Exports** every choice it made to `import.json` so the exact run can be
   reproduced later.

Supported observing bands span the full VLA range: **4, P, L, S, C, X, Ku, K,
Ka, and Q**.

## Features

- **Three ways to run** — a guided Tkinter GUI, an interactive CLI, and a
  fully imported/automated mode.
- **Automatic source resolution** via NED and SIMBAD, including coordinate
  lookup and flux checks.
- **Archive search and download** — `--radio_search` queries the observation archive
  for your source and pulls the segment straight from the Delos NAS, downloading in
  parallel with the calibration prompts.
- **Local data ingest** — or point the tool at a raw VLA archive or an existing
  measurement set and it handles the CASA import.
- **End-to-end CASA calibration** — optional `tfcrop` RFI flagging (with a flag
  backup and a plotms review), then `setjy` → `bandpass` → `gaincal` → `fluxscale`
  → `applycal`, with automatic calibrator selection and an adaptive `applymode`
  chosen from the gaincal solution-failure rate.
- **Imaging with `tclean`** — array-config-aware cell size, LAS-bounded multiscale
  scales, and mode-aware masking (interactive drawing, or `auto-multithresh` when
  automatic).
- **Adaptive self-calibration** — a data-driven solint ladder (`inf` → shortening
  toward the integration time → `int`), phase cycles then a guarded amp+phase pass,
  scored by dynamic range with keep-best and early stopping; faint sources are skipped.
- **Optional baseline calibration** — a guarded `blcal` polish for bright, compact
  sources (opt-in).
- **Per-run results folder** — collects the science products (FITS, primary-beam-
  corrected image, PNG preview, clean mask, listobs, and the CASA log) in one place.
- **Reproducible runs** — every run emits an `import.json` recipe *and* a standalone
  `replay.py` of the exact CASA task calls (with a provenance header) for hands-free,
  mask-aware reproduction.
- **Archive submission** — packages each run into products and calibrated-MS
  tarballs, then opens the group's submission form prefilled from the run's own
  measurements.
- **CPU pinning** — the launcher pins CASA to a per-user set of cores via `taskset`
  to play nicely on shared machines.

## How It Works

```
  Source name  +  observation file (data_archive/)
      │
      ▼
┌───────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Resolve      │────▶│  Import to MS    │────▶│  Calibrate        │
│  (NED/SIMBAD) │     │  + listobs       │     │  (setjy→applycal) │
└───────────────┘     └──────────────────┘     └───────────────────┘
                                                         │
                                                         ▼
┌───────────────┐     ┌──────────────────┐     ┌───────────────────┐
│ Results+replay│◀────│  Self-cal        │◀────│  Image            │
│ (FITS/png/mask│     │  cycles (opt)    │     │  (tclean)         │
│  import/replay)│    │                  │     │                   │
└───────────────┘     └──────────────────┘     └───────────────────┘
```

## Requirements

- **Python 3.10**
- A Linux environment with `taskset` available (the launcher pins CASA to
  specific CPU cores).
- Network access to the NED/SIMBAD catalog services for source resolution.
- A `Creds.json` in the project root, if you intend to use the archive search
  (`--radio_search`) or the submission form (`--archive`) — see
  [Credentials](#credentials).
- All Python dependencies are installed automatically into a dedicated virtual
  environment on first run (see [`requirements.txt`](requirements.txt)). The
  core stack is built on the NRAO **CASA 6.6** modular packages — `casatasks`,
  `casatools`, `casaviewer`, `casaplotms`, and `casaconfig` — alongside NumPy,
  SciPy, and Matplotlib.

## Installation

Each user runs their own clone, with their own virtual environment and their own
`data_archive/`, so runs on a shared machine never collide.

**1. Clone the repository:**

```bash
git clone https://github.com/domo4448/hvla_image_machine ~/hvla_image_machine
```

**2. Add the shell command.** Run once from inside the clone — it appends an
`hvla_image` function to your `~/.bashrc` so you can start a run from any directory:

```bash
cd ~/hvla_image_machine
bash tools/install_alias.sh --cores 25-28
source ~/.bashrc
```

The core list is required; see [CPU cores](#cpu-cores). Use `--rc ~/.zshrc` for zsh,
or `--name` to call the command something else. The script only ever *appends* — it
never edits or deletes anything already in your rc, and does nothing at all if the
block is already there.

**3. Add `Creds.json`** to the project root, if you need the archive search or the
submission form — see [Credentials](#credentials).

The first invocation creates the `.hvla_env` virtual environment, installs all
dependencies, and starts the application; expect several minutes. Subsequent runs
reuse the environment and start immediately.

If you would rather not add a shell function, `bash run.sh` from the repository root
does the same thing — the function exists only so the pipeline can be started from
anywhere, since `run.sh` resolves `.hvla_env`, `src/` and `data_archive/` relative to
the current directory.

## Credentials

The archive search, the NAS download, and the submission form all read a single
`Creds.json` at the **project root**, beside `run.sh`:

```
hvla_image_machine/
├── Creds.json      <- here
├── run.sh
└── src/
```

It is deliberately not in the repository — obtain a copy from the group and drop it in
place. It holds the search host and login, the NAS base URL, the path to the remote
`radio_search` tool, and the submission form URL.
[`classes/creds.py`](src/classes/creds.py) is the only thing that reads it; nothing
else should look for it or keep a second copy.

Without it the pipeline still calibrates and images normally — only `--radio_search`
and `--archive` are affected. The GUI disables its **Get Observations** button when
the file is missing.

## Configuration

### CPU cores

[`run.sh`](run.sh) pins CASA to specific cores via `taskset` so runs share a machine
politely. Your core list lives in the `HVLA_CPU_CORES` value that
`install_alias.sh` wrote into your `~/.bashrc`:

```bash
hvla_image() {
  ( cd "$HOME/hvla_image_machine" && HVLA_CPU_CORES="25-28" bash run.sh "$@" )
}
```

Edit that line and re-source to change it, or override for a single run:

```bash
HVLA_CPU_CORES=1,2 hvla_image
```

Accepted forms: a comma list (`25,26,27,28`), a range (`25-28`), a mix (`0-3,8`), or
empty to disable pinning entirely. With nothing set, `run.sh` falls back to the
default at the top of the file. Pick cores nobody else is using — pinning confines a
run, it does not parallelize it, and two people on the same cores will contend.

### CASA measures data

On a fresh machine without an existing CASA installation, the CASA measures
tables must be downloaded once. In
[`src/HVLA_image_machine.py`](src/HVLA_image_machine.py), uncomment the
`update_config()` call inside `main()` where noted for your first run.

## Providing Observations

Two routes: let the tool find and download the observation for you, or point it at a
file you already have.

### Search and download it — `--radio_search`

With `-rs` the tool queries the observation archive for your source, shows what it
finds, and downloads the segment you pick straight from the Delos NAS into
`data_archive/<proj_code>/`. The transfer runs in parallel with the calibration
prompts, so you answer questions while the files come down:

```bash
hvla_image -rs
```

Needs [`Creds.json`](#credentials), and implies `--cli`. In the GUI the equivalent is
the **Get Observations** button.

### Point it at a local file

Place the data in [`data_archive/`](data_archive/) and select it:

- **Raw VLA archive** — an export file ending in `.exp` or `.dat`
  (e.g. `data_archive/AL727_1_54752.05078_54752.54916.exp`). It is imported to a
  measurement set with CASA's `importvla` on first use. A segment split across
  several files is concatenated into one MS.
- **Existing measurement set** — an already-imported CASA MS ending in `.ms`; the
  import step is skipped.

In the GUI, use the **Browse** button to select the file. In CLI mode, enter the
path when prompted; it must end in `.exp`,`.dat`, or `.ms`. Imported measurement sets are
written to [`measurement_sets/`](measurement_sets/).

## Usage

The default invocation launches the GUI:

```bash
hvla_image                   # or: bash run.sh, from the repository root
```

Pass arguments to select a different mode; they reach the pipeline unchanged either
way:

```bash
hvla_image --cli             # fully interactive terminal mode, no GUI
hvla_image -rs               # search the archive, download, then run
hvla_image --importRun       # replay a previous run from import.json
hvla_image --archive         # submit a finished run to the archive form
```

### Command-line options

| Flag | Alias | Description |
|------|-------|-------------|
| `--radio_search` | `-rs` | Search the observation archive for the source and download it from the NAS instead of supplying a file. Implies `--cli`; needs `Creds.json`. |
| `--cli` | `-c`, `-t` | Run the entire pipeline in the terminal without the GUI. |
| `--cliCalib` | `-tc` | Keeps source selection on the GUI path even alongside `--cli`, and is recorded in the run log. |
| `--importRun` | `-i`, `-import` | Import settings from `import.json` for an automated run. |
| `--noexport` | | Skip writing the `import.json` export. |
| `--archive` | `-a` | Archive submission — prompts for a finished results folder to submit, or press enter to submit this run once it completes. Needs `Creds.json`. |
| `--no-ms-tar` | | Skip the large calibrated-MS tarball; the products tarball is still written. |
| `--debug` | | Also write `export_for_testing.json`, a full dump of the options object. |

> **Note:** argument abbreviation is enabled, so `--no` is ambiguous between
> `--noexport` and `--no-ms-tar`. Type enough of the flag to be unique.

## Archiving and Submission

When a run finishes it packages its results folder into two tarballs, written beside
the products:

| Bundle | Contents |
|--------|----------|
| `<name>_results.tar.gz` | everything a reviewer reads — FITS, pbcor image, PNG preview, `<name>.fit.json`, run log, `replay.py` |
| `<name>_CALMS.tar.gz` | the calibrated measurement set, kept separate because it is far larger |

Use `--no-ms-tar` when you only need the products bundle.

`--archive` then opens the group's submission form in a browser, prefilled from the
run: source name and coordinates, band, array configuration, resolution, and the
measured fit values. File uploads cannot be prefilled — attach the tarballs yourself.

```bash
hvla_image -a
```

It prompts for a results folder. Give it one and it submits that finished run and
exits; press enter instead and it runs the pipeline normally, submitting at the end.
Archiving an older folder recovers the measurements from its `<name>.fit.json` and the
observation from its saved listobs, so a run archived weeks later needs nothing but
the folder itself. Needs [`Creds.json`](#credentials), which holds the form URL.

## Reproducible Runs

Every successful run writes an `import.json` capturing the source, band,
calibrator choices, imaging parameters, and breakpoints. Replay that exact run
with:

```bash
bash run.sh --importRun
```

A blank template is available under
[`parsing_examples/`](parsing_examples/) for reference. Use `--noexport` to skip
generating the file on a given run.

Alongside the recipe, each run also drops a standalone **`replay.py`** into the
results folder — the exact sequence of CASA task calls it executed, every parameter
resolved to a literal, with a provenance header (CASA/Python versions and git commit).
Where `import.json` re-runs the pipeline's *decision logic*, `replay.py` reproduces
the *process* directly and non-interactively, reusing any clean mask that was drawn
(the mask is saved to the results folder and referenced from `import.json` too).

## Project Structure

```
src/
├── HVLA_image_machine.py      # Application entry point & orchestration
├── Dependencies.py            # Auto-installs requirements into the venv
├── pre_calibration/           # GUI, option parsing, and import/export
│   ├── hvla_gui.py            #   Tkinter source-input interface
│   ├── options_class.py       #   Central Options/run-configuration object
│   └── import_settings.py     #   import.json read/write
├── classes/                   # Core domain models & shared utilities
│   ├── source_class.py        #   Source & calibrator resolution
│   ├── observations_class.py  #   Observation/listobs data model
│   ├── CLI_input.py           #   Interactive terminal prompts
│   ├── decisions.py           #   Decision-point modes (auto/verify/manual/...)
│   ├── creds.py               #   Creds.json location + loading (the only reader)
│   ├── run_log.py             #   Human-readable report of the run's choices
│   ├── call_recorder.py       #   Records CASA calls -> replay.py
│   └── constants.py           #   Band tables, defaults, decision registry
├── API_integrations/          # External catalog clients
│   ├── NED.py                 #   NED queries + self-cal flux check
│   └── simbad.py              #   SIMBAD queries
├── archive_dowload/           # Observation archive search & download
│   └── radio_search_integration.py  #   radio_search query + Delos NAS download
├── archive/                   # Run packaging & archive submission
│   ├── results_package.py     #   products / calibrated-MS tarballs
│   └── form_submission.py     #   submission form, prefilled from the run
├── data_calibration/          # CASA calibration pipeline
│   ├── hvla_data_cal.py       #   Calibration entry point
│   ├── main_calibrations.py   #   setjy/bandpass/gaincal/fluxscale/applycal + failure-rate applymode
│   ├── data_flagging.py       #   tfcrop flagging breakpoint (backup + plotms review)
│   └── parse_listobs.py       #   listobs parsing + array-config / solint helpers
└── image_generation/          # CASA imaging
    ├── image_maker.py         #   tclean, self-cal ladder, results folder + replay
    └── source_fit.py          #   2D Gaussian fit of the target -> <name>.fit.json

tools/
└── install_alias.sh           # One-time shell-function setup (see Installation)
```

Each run's results folder collects the science products (FITS, pbcor, PNG, mask,
listobs, CASA log), the structured measurements (`<name>.fit.json`), the exact CASA
calls (`replay.py`), and `<name>.log`, a human-readable report of what the run decided
and why — then bundles the lot into the tarballs described in
[Archiving and Submission](#archiving-and-submission). The `import.json` recipe is
written to the **project root**, not the results folder, and is overwritten by each
run.

## Roadmap

Active development items (see [`TODO`](TODO) for the full list):

- Core subtraction for imaging, and multi-component Gaussian fitting (the fit
  currently models one component at the peak).
- Principled reference-antenna selection (central, low-flagging, present for the
  full track) and a fluxscale-failure retry.
- Manual flux calibration and a "skip self phase-cal" toggle.
- A guided manual self-cal mode (inspect solutions / choose solint per cycle).
- Outlier-field imaging.
- Expanded GUI features and clearer separation of manual self-cal from
  interactive cleaning.


---

> **Note:** This project is under active development. Interfaces and behavior
> may change between runs.
