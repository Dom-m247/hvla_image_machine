# HVLA Image Machine

**An automated calibration and imaging pipeline for archival VLA radio-interferometry data.**

The HVLA Image Machine takes a radio source by name and your raw observation
data, then drives the full [CASA](https://casa.nrao.edu/) workflow — from raw
archive to a science-ready image — with sensible defaults and minimal manual
intervention. It is designed to make reducing historical VLA observations
approachable through a guided GUI, a scriptable CLI, and fully reproducible
JSON-based run configurations.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Providing Observations](#providing-observations)
- [Usage](#usage)
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
- **Local data ingest** — point the tool at a raw VLA archive or an existing
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
- **CPU pinning** — the launcher pins CASA to a configurable set of cores via
  `taskset` to play nicely on shared machines.

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
- All Python dependencies are installed automatically into a dedicated virtual
  environment on first run (see [`requirements.txt`](requirements.txt)). The
  core stack is built on the NRAO **CASA 6.6** modular packages — `casatasks`,
  `casatools`, `casaviewer`, `casaplotms`, and `casaconfig` — alongside NumPy,
  SciPy, and Matplotlib.

## Installation

Clone the repository and run the launcher. On first invocation it creates the
`.hvla_env` virtual environment, installs all dependencies, and starts the
application:

```bash
git clone https://github.com/domo4448/hvla_image_machine
cd hvla_image_machine
bash run.sh
```

Subsequent runs reuse the existing environment and start immediately.

## Configuration

### CPU cores

[`run.sh`](run.sh) pins CASA to specific cores via `taskset`. **Edit the
`CPU_CORES` variable** to match your machine before running (or remove the
pinning entirely if you don't need it):

```bash
CPU_CORES="25,26,27,28"   # change to cores available on your system
```

### CASA measures data

On a fresh machine without an existing CASA installation, the CASA measures
tables must be downloaded once. In
[`src/HVLA_image_machine.py`](src/HVLA_image_machine.py), uncomment the
`update_config()` call inside `main()` where noted for your first run.

## Providing Observations

The pipeline reads observations from the [`data_archive/`](data_archive/)
directory. Place your data there before running and point the tool at it:

- **Raw VLA archive** — a single export file ending in `.exp`
  (e.g. `data_archive/AL727_1_54752.05078_54752.54916.exp`). It is imported to a
  measurement set with CASA's `importvla` on first use.
- **Existing measurement set** — an already-imported CASA MS ending in `.ms`.

In the GUI, use the **Browse** button to select the file. In CLI mode, enter the
path when prompted; it must end in `.exp`,`.dat`, or `.ms`. Imported measurement sets are
written to [`measurement_sets/`](measurement_sets/).

## Usage

The default invocation launches the GUI:

```bash
bash run.sh
```

Pass arguments through `run.sh` to select a different mode:

```bash
bash run.sh --cli            # fully interactive terminal mode, no GUI
bash run.sh --importRun      # replay a previous run from import.json
```

### Command-line options

| Flag | Alias | Description |
|------|-------|-------------|
| `--importRun` | `-i`, `-import` | Import settings from `import.json` for an automated run. |
| `--cli` | `-c`, `-t` | Run the entire pipeline in the terminal without the GUI. |
| `--cliCalib` | `-tc` | CLI mode for calibration and imaging with manual calibrator override. |
| `--archive` | `-a` | After imaging, open the archive submission form prefilled from the run. |
| `--noexport` | | Skip writing the `import.json` export. |
| `--debug` | | Use debug exports for testing. |

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
│   ├── call_recorder.py       #   Records CASA calls -> replay.py
│   └── constants.py           #   Band tables, defaults, calibrator maps
├── API_integrations/          # External catalog clients
│   ├── NED.py                 #   NED queries
│   └── simbad.py              #   SIMBAD queries
├── data_calibration/          # CASA calibration pipeline
│   ├── hvla_data_cal.py       #   Calibration entry point
│   ├── main_calibrations.py   #   setjy/bandpass/gaincal/fluxscale/applycal + failure-rate applymode
│   ├── data_flagging.py       #   tfcrop flagging breakpoint (backup + plotms review)
│   └── parse_listobs.py       #   listobs parsing + array-config / solint helpers
└── image_generation/          # CASA imaging
    ├── image_maker.py         #   tclean, self-cal ladder, results folder + replay
    └── source_fit.py          #   2D Gaussian fit of the target -> <name>.fit.json
```

Each run's results folder collects the science products (FITS, pbcor, PNG, mask,
listobs, CASA log), the structured measurements (`<name>.fit.json`), a
reproducible recipe (`import.json`) and the exact CASA calls (`replay.py`) — plus
`<name>.log`, a human-readable report of what the run decided and why.

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
