# Branch `p-band-experimental`: what changed and why

Based on `harness-scheduling` (which is based on `lightcurve-fixes`). **Draft, not for
merging yet**: this adds P band, the VLA's lowest-frequency band we can use, and it has
not been tested on real data. Most of the code makes sure it can't run, or be mistaken
for a trustworthy result, without a person watching.

To review: `git diff harness-scheduling..p-band-experimental`. A glossary of the radio
terms is at the end.

---

## Why P band needs special treatment

Every band so far (L through Q: 1–50 GHz) behaves similarly enough that one automatic
recipe works. P band (~327 MHz, wavelength 90 cm) is different in ways that break the
recipe's assumptions:

| Problem at 90 cm | What it does to the automatic pipeline |
|---|---|
| **RFI** (radio interference from phones, TV, radar, power lines) is much worse | automatic flagging can remove good data or keep bad data; someone has to look |
| **The ionosphere** bends and delays the signal, differently in different directions | calibration that assumes one correction per antenna for the whole field is wrong, worst in the largest (A) configuration |
| **The field of view is huge** (~150 arcmin primary beam, 2.5°) | 1024-pixel images don't cover it; many more bright sources in the field |
| **CASA's beam model is too narrow at P band** (131′ vs. the real ~150′) | fluxes of sources away from the centre come out too high |
| **The usual flux standard (Perley-Butler 2013) is fitted only above 1 GHz** | the flux scale would be extrapolated outside the model's range |

So the branch is in two parts: (1) **guard rails**, so P band only runs with a person
watching and every output is labelled; (2) **P-band parameters**, the per-band numbers
the pipeline needs.

## 1. Guard rails: "experimental band" as a concept

One new constant drives everything:

```python
# src/classes/constants.py
EXPERIMENTAL_BANDS = ('P',)
```

Any band in that tuple gets the treatment below. Nothing is hard-coded to `'P'`, so the
same guards would apply to another band later, and removing `'P'` from the tuple turns
them off.

### The pipeline refuses to run unattended — `decisions.require_attended()`

`src/classes/decisions.py`. Called twice in `hvla_data_cal.py`: once at the start of
`pre_data_calibration` (band known from the GUI/CLI/import.json), and again in
`set_calibrators` (band only worked out from the data). It acts once.

- `why_unattended()` checks for a person: a `DISPLAY` (the mask-drawing viewer and plotms
  are GUI windows) and a terminal on stdin (`sys.stdin.isatty()`, for prompts).
- Missing either → `sys.exit("Stopping: P band is experimental and runs only attended …")`
  **before anything is calibrated**. No half-finished output.
- Present → sets `options.attended = True` and makes the run interactive:
  - `interactive_image = True`: the person draws the clean masks (marks which pixels are
    real sources).
  - flagging `auto` → `verify`: after the automatic RFI flagging, the person checks the
    result in plotms and keeps or reverts it.
  - prints a big `*** EXPERIMENTAL: P BAND ***` banner and records it in the run log.
- `is_interactive()` now returns `True` when `options.attended` is set, even under
  `--importRun`. Normally `--importRun` means "replay a saved recipe without asking
  anything". The attended harness preset uses `--importRun`, but a person is present, so
  the prompts are allowed.

### The harness skips P band in unattended sweeps — `selection.attended_only()`

`harnesses/harness/selection.py`, used by both harness kinds (`kinds/lightcurve.py`,
`kinds/full_auto.py`). Same signature as the existing `within_size()` filter: returns
`(kept, rejected)`. In an unattended sweep each P-band observation goes into `rejected`
with the reason `P band is experimental: attended runs only (--preset lightcurve_deep)`.
It shows up in the sweep's skipped list and oversight log, and the other bands run as
normal. The pipeline's own `sys.exit` is a second safety net behind this.

One ordering fix in `kinds/lightcurve.py`: sorting by date now happens before the
filters, so the rejected list is in date order too.

### Every output is labelled

A P-band number must never end up on a plot looking like a normal measurement:

| Output | Label |
|---|---|
| run log (`run_log.py`) | `*** EXPERIMENTAL: P BAND ***` banner at the top; A-configuration warning; `*** EXPERIMENTAL ***` next to the band |
| `fit.json` (`source_fit.py`) | `"experimental": "P band"` key; summary printed at the end starts with the warning |
| lightcurve CSV (`lightcurve_plot.py`) | new `experimental` column; `note` starts with `EXPERIMENTAL P band (unvetted)`. Filled in from the band too, so a run without the `fit.json` key is still caught |
| lightcurve plot | diamonds / half-filled triangles instead of circles / triangles; legend entry and panel title say EXPERIMENTAL |
| GUI and CLI band pickers | listed as `P (experimental)`; the CLI prints a "stay at the terminal" note when you choose it. `SourceInputWindow._band()` strips the label before the pipeline sees the value |

In `lightcurve_plot.py`, the old `_catalogue(row)` check (2 kinds of mark) became
`_mark(row)` → `'standard' | 'catalogue' | 'experimental'` (3 kinds). Experimental takes
priority, so a P-band point is never drawn with a vetted mark.

## 2. P-band parameters

All in `constants.py`, as **per-band override dicts** next to the existing defaults, read
with `.get(band, default)`. The other bands' numbers don't change.

| Constant | Default | P band | Why |
|---|---|---|---|
| `BAND_GHZ_RANGES` / `BAND_MHZ_RANGES` | — | `0.2–0.5 GHz` | P band was missing, so it couldn't be selected or sized |
| `PB_FWHM_ARCMIN_GHZ_BAND` | 45′/GHz | 49′/GHz | P band's feeds see a wider field: 150′ at 327 MHz |
| `MAIN_IMAGE_PIXELS_BAND` | 1024 | 4096 | 1024 pixels cover only 19′/63′/205′ in A/B/C configuration vs. a 150′ beam |
| `OUTLIER_MAX_FWHMS_BAND` | 1.0 | 0.85 | CASA's narrower beam model ends sooner; it can't image an outlier field past it |
| `PB_RELIABLE_FWHMS_BAND` | 0.75 | 0.4 | CASA's model and the real beam differ by >10% beyond 60′: warn |
| `FLUX_STANDARD_BAND` | Perley-Butler 2013 | Perley-Butler 2017 | 2017 is fitted down to 50 MHz; others stay on 2013 so earlier results don't shift |
| `CASA_PB_FWHM_ARCMIN_GHZ` | — | 43′/GHz | only used in messages, to say how far CASA's model differs |

Code using them:

- `image_maker.Cleaner.plan_field` — beam size, image size and outlier limit from the
  dicts above. The plan now carries `outlier_max_fwhms` so the three places that checked
  `OUTLIER_MAX_FWHMS` use the band's value. Notes in the run log that off-axis P-band fluxes
  come out too high; warns about A configuration.
- `hvla_data_cal.build_setjy` — flux standard by band.
- `source_fit._field_warnings` — the "target too far off-centre to trust" threshold by band.
- `selection.py` — comment update only: P now has table entries, only the 4 band (74 MHz)
  can't be sized.

## Docs

README (supported bands list, new "P band (experimental)" section), `harnesses/HARNESS.md`
(how a sweep treats P band, how to run it attended) and `TODO` (what the first live
sessions must check, using test data set AD0308).

## Status / what we need from you

- **Not tested end-to-end.** It compiles, and the guard rails were checked by reading the
  code, not by a full live run. The `TODO` lists a known blocker: AD0308's field names
  contain spaces (`'NGC 4565_1'`), which `parse_listobs`'s regexes don't accept.
- Code review welcome, especially: the `require_attended` / `is_interactive` interplay
  with `--importRun`, and whether the per-band-dict pattern is how you'd like per-band
  settings done generally.
- Please keep it out of `main` until a live session has gone through the `TODO` list.

---

## Glossary (for this branch)

- **Band**: a range of radio frequencies the telescope has receivers for. Named by letter:
  P ≈ 0.3 GHz, L ≈ 1.5 GHz, C ≈ 6 GHz, X ≈ 10 GHz … Q ≈ 45 GHz. Lower frequency =
  longer wavelength = blurrier images and a bigger patch of sky.
- **VLA configuration (A/B/C/D)**: the VLA's 27 dish antennas sit on rails and are moved
  every few months. A = spread out over 36 km (sharpest images), D = packed in 1 km.
  Wider spacing = finer detail, the same way a bigger lens gives a sharper photo.
- **Primary beam**: the patch of sky one dish can see at once. Sensitivity is highest at
  the centre and falls off (roughly a Gaussian bump) towards the edge. FWHM ("full width
  at half maximum") is its diameter where sensitivity drops to 50%. Its size ∝ wavelength:
  ~30′ at L band, ~150′ at P band.
- **Primary-beam correction (pbcor)**: dividing the image by the beam's sensitivity so a
  source near the edge gets its true brightness back. If the beam model is wrong, the
  corrected flux is wrong, which is the P-band problem here.
- **Synthesized beam / cell size**: the resolution of the final image (the smallest blob a
  point source becomes). The pipeline uses 5 pixels across one beam.
- **Flux density (Jy, mJy)**: how bright a source is at radio wavelengths. A lightcurve
  is flux density against time.
- **Flux calibrator / flux standard**: a few very stable bright sources (3C286, 3C48 …)
  whose brightness at each frequency is published as a fitted formula
  ("Perley-Butler 2013/2017"). The pipeline observes one to set the brightness scale for
  everything else (CASA task `setjy`).
- **Calibration / self-calibration**: estimating each antenna's gain and phase errors
  over time and removing them. Self-cal uses a model of the target field itself to do it,
  which is why every bright source in the field has to be in the model.
- **Ionosphere**: the charged upper atmosphere. At low frequency it delays the signal
  by different amounts in different directions. "Not isoplanatic" = one correction per
  antenna is not valid across the whole field, worst in A configuration.
- **RFI / flagging**: radio frequency interference from human transmitters. Flagging means
  marking corrupted data points to be ignored (`tfcrop` is CASA's automatic flagger;
  `plotms` is its plotting GUI where a person inspects them).
- **Cleaning / clean mask**: the image as first made from the data is blurred by the
  array's pattern. `tclean` deconvolves it. The mask tells it which regions contain real
  emission. Normally automatic here; at P band a person draws it.
- **Outlier fields**: small extra images around bright sources outside the main image,
  so their sidelobes (artifacts that spread across the image) can be cleaned too.
- **NVSS, TGSS**: sky surveys (1.4 GHz and 150 MHz) used as catalogues of where bright
  sources are and roughly how bright.
- **MS (Measurement Set)**: CASA's on-disk format for the raw data. **listobs**: CASA's
  summary of what's in it.
