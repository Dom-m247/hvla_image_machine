from classes import image_data
from pre_calibration.options_class import Options
from classes.constants import *
from data_calibration import main_calibrations
from data_calibration import parse_listobs as parse
from image_generation import source_fit
from classes import run_log
from typing import Any
from pathlib import Path
import casatasks as ct
import casashell
import shutil
from classes.Loading_Animation import *
#I(this script) am so FULL of magic numbers 🥰 that are absolutley pulled from thin Air 

class Cleaner:
  @staticmethod
  def _mask_kwargs(options:Options, mask=None, nsigma=None) -> dict[str, Any]:
    '''tclean masking/stop params for the self-cal cleans. Precedence:

      1. a saved mask (`mask` arg, else options.mask) on disk -> usemask='user'.
         Loaded to refine when interactive, replayed hands-free when not.
      2. interactive imaging -> the user draws the mask (nsigma just stops).
      3. automatic imaging   -> CASA auto-multithresh builds the mask.

    nsigma stops cleaning at the noise floor in every case: the model this clean
    writes feeds the next gaincal, so noise in it corrupts the solution. `nsigma`
    overrides the default depth (see _nsigma_for_solint).
    '''
    kw: dict[str, Any] = {'nsigma': SELF_CAL_NSIGMA if nsigma is None else nsigma}
    use_mask = mask or getattr(options, 'mask', '')
    if use_mask and Path(str(use_mask)).exists():
      kw['usemask'] = 'user'
      kw['mask'] = str(use_mask)
    elif not options.interactive_image:
      kw['usemask'] = 'auto-multithresh'
    return kw

  @staticmethod
  def _mask_path(image_base):
    '''The tclean mask an image cycle wrote (<base>.mask), or '' if none exists.'''
    mask = image_base + '.mask'
    return mask if Path(mask).exists() else ''

  @staticmethod
  def _tclean_kwargs(options:Options) -> dict[str, Any]:
    '''tclean params shared by every imaging cycle, so the initial clean and the cycles
    scored against it are made identically. Callers add imagename, niter and the mask
    kwargs. Needs options.cell_size set (find_cell_size, in initial_cycle).'''
    return {
      'vis': options.calibrated_filename + '.ms',
      'deconvolver': options.deconvolver,
      'smallscalebias': CLEAN_SMALL_SCALE_BIAS,
      'weighting': options.weighting,
      'robust': getattr(options, 'robust', CLEAN_ROBUST),
      'interactive': options.interactive_image,
      'savemodel': 'modelcolumn',
      'nterms': CLEAN_NTERMS,
      'scales': Cleaner._multiscale_scales(options),
      'cell': options.cell_size,
      'imsize': options.image_size,
      'pblimit': CLEAN_PBLIMIT,
    }

  @staticmethod
  def initial_cycle(options:Options, niter=CLEAN_NITER):
    '''The initial clean: the baseline every self-cal cycle is scored against. Same
    params as the cycles (_tclean_kwargs); niter is the deliberate exception.'''
    options.cell_size = Cleaner.find_cell_size(options)
    #Same stop/mask treatment as every other clean: nsigma stops at the noise floor and
    #auto-multithresh masks when imaging automatically, so an auto run is reproducible
    #without a human. Interactive runs draw their own mask instead (_mask_kwargs).
    mask_kwargs = Cleaner._mask_kwargs(options)
    if options.do_self_cal:
      #shallow: this model only has to feed the first gaincal, not be a finished image
      niter = SELF_CAL_INITIAL_NITER
    #add nmajor=1/2 instead of lowering niter?
    ct.tclean(imagename=options.image_filename,
                  niter=niter,
                  **Cleaner._tclean_kwargs(options),
                  **mask_kwargs
                  #mask='circle[[800pix,800pix],600pix]'
                  )
    ct.impbcor(imagename=options.image_filename+'.image.tt0',
               pbimage=options.image_filename+'.pb.tt0',
               outfile=options.image_filename+'.pbcorimage',
               overwrite=True)
    Cleaner.export_png(options.image_filename)
    #RMS/improvement score is measured on the flat-noise restored image, not the
    #pbcor image (whose noise blows up toward the edges and would skew the RMS).
    return ct.imstat(imagename=options.image_filename+'.image.tt0')
  
  @staticmethod
  def _clean_and_measure(options:Options, label, mask=None, nsigma=None):
    '''Clean the (re-calibrated) source MS into <image_filename>_<label>, pbcor + PNG
    it, and return imstat on the flat-noise restored image. Shared by the self-cal and
    baseline-cal cycles; images identically to the initial clean (_tclean_kwargs).

    `mask`: a saved/carried mask to reuse for this clean (see _mask_kwargs).'''
    name = options.image_filename + '_' + str(label)
    ct.tclean(imagename=name,
                  niter=CLEAN_NITER,
                  **Cleaner._tclean_kwargs(options),
                  **Cleaner._mask_kwargs(options, mask, nsigma)
    )
    ct.impbcor(imagename=name+'.image.tt0', pbimage=name+'.pb.tt0',
               outfile=name+'.pbcorimage', overwrite=True)
    Cleaner.export_png(name)
    #flat-noise restored image for a consistent, uniform-noise RMS (see initial_cycle)
    return ct.imstat(imagename=name+'.image.tt0')

  @staticmethod
  def self_cal_cycle(options:Options,iter,solint='inf',calmode='p',mask=None,nsigma=None):
    '''
    Runs a single automated cycle of self calibration.

    solint : gaincal solution interval for this cycle (loop shortens it as SNR builds).
    calmode: 'p' for phase-only cycles, 'ap' for the final amplitude+phase pass.
    mask   : a saved/carried clean mask to reuse (so interactive users draw once).
    nsigma : clean depth for this cycle; None = the default (see _mask_kwargs).
    '''
    iter = str(iter)
    #calibration cycle -- model column feeding gaincal comes from the previous clean
    LoadingAnimation.performing_action(action=f'self-cal cylce {iter} (solint={solint}, calmode={calmode})',
                                       target=main_calibrations.self_cal_cycle,
                                       args=(options,iter,solint,calmode))
    return Cleaner._clean_and_measure(options, iter, mask=mask, nsigma=nsigma)

  @staticmethod
  def baseline_cal_cycle(options:Options, label='blcal', mask=None):
    '''Run the final baseline-based (blcal) calibration, then image like a self-cal
    cycle. The caller gates this on a bright source and keeps the result only if it
    improves the dynamic range without losing flux (blcal can overfit).'''
    LoadingAnimation.performing_action(action='baseline calibration (blcal)',
                                       target=main_calibrations.baseline_cal,
                                       args=(options,))
    return Cleaner._clean_and_measure(options, label, mask=mask)

  @staticmethod
  def test_image_cycle(options:Options):
    '''Shallow clean shown before the real imaging so cell size, image size and robust
    can be judged on this data. Loops until the user keeps the parameters; the images
    are scratch. No-op unless options.test_image is set.

    Runs before any scored imaging, so changing parameters here cannot make the
    keep-best dynamic ranges incomparable.'''
    from classes import decisions
    if not getattr(options, 'test_image', False):
      return
    options.cell_size = Cleaner.find_cell_size(options)
    attempt = 0
    while True:
      name = f"{options.image_filename}{TEST_IMAGE_SUFFIX}{attempt or ''}"
      Cleaner._clear_image(name)  #a test image is always a fresh look, never a restart
      print(f"\nTest image {attempt + 1}: cell={options.cell_size}, "
            f"imsize={options.image_size}, robust={options.robust}")
      ct.tclean(**{**Cleaner._tclean_kwargs(options), 'imagename': name,
                   'niter': TEST_IMAGE_NITER, 'interactive': False,
                   **Cleaner._mask_kwargs(options)})
      Cleaner.export_png(name)
      measured = image_data.Image(options, ct.imstat(imagename=name+'.image.tt0'), base=name)
      peak, rms = measured.peak(), measured.off_source_rms()
      if peak is not None and rms:
        print(f"  peak {peak:.4g} Jy/beam, off-source rms {rms:.4g}, DR {peak/rms:.1f}")
      if not decisions.confirm("Adjust and re-image?"):
        break
      #blank keeps the current value
      options.cell_size = Cleaner._as_arcsec(
        decisions.value('Cell size (arcsec)', options.cell_size))
      size = decisions.value('Image size (pixels)', options.image_size[0], int)
      options.image_size = [size, size]
      options.robust = decisions.value('Robust', options.robust, float)
      attempt += 1
    #the settled cell must survive initial_cycle's find_cell_size, which otherwise
    #recomputes it from the band table and discards what was just chosen
    options.use_custom_cell_size = True
    run_log.note('IMAGING', 'Test image',
                 f"{attempt + 1} pass(es); kept cell={options.cell_size}, "
                 f"imsize={options.image_size}, robust={options.robust}")

  @staticmethod
  def _clear_image(base):
    '''Delete a previous run's tclean products for this image base.

    tclean refuses to start when an existing <base>.mask sits beside an explicit
    mask= selection, and would otherwise restart from stale residuals.'''
    for path in sorted(Path().glob(base + '.*')):
      try:
        ct.rmtables(str(path)) if path.is_dir() else path.unlink()
      except Exception as e:
        print(f"could not remove {path}: {e}")

  @staticmethod
  def _core_mask(options, image):
    '''Region string masking a circle of CORE_MASK_BEAMS beams around the image peak,
    or '' when the peak/beam geometry is unreadable.'''
    header = image.header()
    shape, peak = image_data.image_shape(header), image.peak_pixel()
    beam, cell = image_data.beam_from_header(header), image_data.pixel_scale_arcsec(header)
    if not (shape and peak and beam and cell and cell > 0):
      print("core subtraction: peak or beam unreadable; cannot build a core mask.")
      return ''
    radius = max(3, int(CORE_MASK_BEAMS * beam['major_arcsec'] / cell))
    return f"circle[[{peak[0]}pix,{peak[1]}pix],{radius}pix]"

  @staticmethod
  def core_subtract_cycle(options:Options, image):
    '''Clean only the core into the model, uvsub it out of a copy of the MS, then image
    what is left -- the jet. Returns the coresub image base, or '' if it did not run.

    Works on a copy so the calibrated MS keeps its own MODEL/CORRECTED columns intact.
    '''
    mode = options.decision('core_subtract')
    if mode == OFF:
      return ''
    vis = options.calibrated_filename + '.ms'
    if not Path(vis).is_dir():
      print(f"core subtraction: no calibrated MS at {vis}; skipping.")
      return ''

    #manual: the user circles the core themselves (1.99's behavior). auto: a circle of
    #CORE_MASK_BEAMS around the fitted peak.
    interactive = mode == MANUAL
    core_mask = '' if interactive else Cleaner._core_mask(options, image)
    if not interactive and not core_mask:
      return ''
    if interactive:
      print("\nCore subtraction: clean ONLY the core -- whatever you clean is what gets "
            "subtracted.")
    else:
      #auto places the mask on the peak sight-unseen, so a faint peak means it may be
      #modelling noise. Warned, not skipped: this is a product the user asked for.
      peak = image.peak()
      if peak is not None and peak < MIN_FLUX_FOR_CORE_SUBTRACT:
        faint = (f"peak {peak:.3g} Jy/beam is below the {MIN_FLUX_FOR_CORE_SUBTRACT} "
                 f"Jy/beam floor -- the auto core mask may be modelling noise, so the "
                 f"subtracted image may not be meaningful")
        print(f"WARNING: {faint}.")
        ct.casalog.post(f"Core subtraction: {faint}", priority='WARN')
        run_log.note('IMAGING', 'Core subtraction warning', faint)

    sub_vis = options.calibrated_filename + '_sub.ms'
    if Path(sub_vis).is_dir():
      shutil.rmtree(sub_vis)
    shutil.copytree(vis, sub_vis)  #filesystem copy, so replay.py cannot reproduce this step

    shared = Cleaner._tclean_kwargs(options)
    core_base = options.image_filename + '_core'
    name = options.image_filename + CORE_SUBTRACT_SUFFIX
    #a previous run's products would make tclean reject the mask selection, or restart
    #from its stale residuals -- both cleans want a clean slate
    Cleaner._clear_image(core_base)
    Cleaner._clear_image(name)
    #1) model the core only -- savemodel writes it into the copy's MODEL column
    ct.tclean(**{**shared, 'vis': sub_vis, 'imagename': core_base,
                 'interactive': interactive, 'niter': CLEAN_NITER,
                 'nsigma': SELF_CAL_NSIGMA,
                 **({'usemask': 'user', 'mask': core_mask} if core_mask else {})})
    #2) subtract that model from the corrected data
    LoadingAnimation.performing_action(action='uvsub (core subtraction)',
                                       target=ct.uvsub, args=(sub_vis,))
    #3) image what is left
    ct.tclean(**{**shared, 'vis': sub_vis, 'imagename': name, 'niter': CLEAN_NITER,
                 **Cleaner._mask_kwargs(options)})
    ct.impbcor(imagename=name+'.image.tt0', pbimage=name+'.pb.tt0',
               outfile=name+'.pbcorimage', overwrite=True)
    Cleaner.export_png(name)
    jet = image_data.Image(options, ct.imstat(imagename=name+'.image.tt0'), base=name)
    peak = jet.peak()
    shown = f"{peak:.4g} Jy/beam" if peak is not None else 'unmeasurable'
    run_log.note('IMAGING', 'Core subtraction',
                 f"{mode}: core modelled{'' if interactive else f' inside {core_mask}'}, "
                 f"uvsub applied; jet peak {shown}")
    print(f"Core-subtracted image: {name} (peak {shown})")
    options.coresub_base = name
    return name

  @staticmethod
  def _scan_timing(vis):
    '''Return (integration_time_s, scan_length_s) for a MS from its scan timestamps
    (via msmd), or (None, None) if they can't be read. Integration time = smallest
    positive gap between successive integrations; scan length = span of a scan; both
    taken as the median across scans.'''
    import numpy as np
    import casatools
    msmd = casatools.msmetadata()
    try:
      if not msmd.open(vis):
        return None, None
      scans = list(msmd.scannumbers())
      if not scans:
        return None, None
      durations, int_times = [], []
      for s in scans:
        t = np.unique(np.asarray(msmd.timesforscan(s), dtype=float))
        if t.size >= 1:
          durations.append(float(t.max() - t.min()))
        if t.size >= 2:
          gaps = np.diff(t); gaps = gaps[gaps > 0]
          if gaps.size:
            int_times.append(float(gaps.min()))
      int_time = float(np.median(int_times)) if int_times else None
      scan_len = float(np.median(durations)) if durations else None
      return int_time, scan_len
    except Exception as exc:
      print(f"solint schedule: could not read scan timing from {vis}: {exc}")
      return None, None
    finally:
      try:
        msmd.close()
      except Exception:
        pass

  @staticmethod
  def _build_solint_schedule(n, int_time_s, scan_len_s, factor=SELF_CAL_SOLINT_FACTOR):
    '''n-cycle phase-only solint ladder: 'inf' (per-scan, best SNR) -> geometric
    shortening by `factor` from ~half a scan down to ~the integration time -> 'int'
    (per-integration, repeated to fill n). Solutions can't be shorter than one
    integration, so the ladder floors there rather than at 1s.'''
    if n <= 0:
      return []
    sched = ['inf']
    floor = max(int_time_s, 1.0)
    t = scan_len_s / factor
    while len(sched) < n and t > floor * 1.5:
      s = f"{round(t)}s"
      if s != sched[-1]:  #avoid a duplicate after rounding
        sched.append(s)
      t /= factor
    while len(sched) < n:  #remainder: iterate at the finest interval
      sched.append('int')
    return sched[:n]

  @staticmethod
  def _solint_schedule(options:Options, n):
    '''Phase-only solint ladder for n self-cal cycles, built for THIS observation
    from its scan/integration times. Falls back to the fixed SELF_CAL_SOLINTS ladder
    (padded with 'int') when the times can't be read -- and logs that to the CASA log.'''
    vis = options.calibrated_filename + '.ms'
    int_time, scan_len = Cleaner._scan_timing(vis)
    if int_time and scan_len and scan_len > int_time:
      sched = Cleaner._build_solint_schedule(n, int_time, scan_len)
      msg = (f"Self-cal solint schedule for {n} cycles "
             f"(int={int_time:g}s, scan={scan_len:g}s): {sched}")
      print(msg)
      ct.casalog.post(msg, priority='INFO')
      run_log.note('IMAGING', 'Solint schedule',
                   f"{sched}   (derived from this observation: integration {int_time:g}s, "
                   f"scan {scan_len:g}s)")
      return sched
    #fallback: fixed ladder, padded with 'int' -- flag it in the log so it's visible
    #that the schedule was NOT derived from this observation's timing.
    sched = list(SELF_CAL_SOLINTS[:n])
    while len(sched) < n:
      sched.append('int')
    msg = (f"Self-cal solint: could not read scan/integration times from {vis} "
           f"(int_time={int_time}, scan_len={scan_len}); using FIXED fallback ladder: {sched}")
    print(msg)
    ct.casalog.post(msg, priority='WARN')
    run_log.note('IMAGING', 'Solint schedule',
                 f"{sched}   (FIXED FALLBACK -- scan/integration times could not be "
                 f"read from the MS, so this was NOT derived from the observation)")
    return sched

  @staticmethod
  def _nsigma_for_solint(solint) -> float:
    '''Clean depth for a phase cycle, from its solint: a long solint means a poorer
    model, so stop further above the noise. Keyed on solint rather than cycle number,
    so a user-chosen solint still gets the matching depth.'''
    s = str(solint).strip().lower()
    if s == 'inf':
      return SELF_CAL_NSIGMA_INF
    if s == 'int':
      return SELF_CAL_NSIGMA
    try:
      seconds = float(s.rstrip('s'))
    except ValueError:
      return SELF_CAL_NSIGMA
    return SELF_CAL_NSIGMA_LONG if seconds > SELF_CAL_LONG_SOLINT_S else SELF_CAL_NSIGMA

  @staticmethod
  def _propose_cycle_params(options:Options, i, schedule) -> dict[str, Any]:
    '''Params for phase cycle i: what automatic mode runs, and what an interactive mode
    would offer as the default for the user to accept or override. Clamps to the last
    solint so an open-ended loop never runs off the end of the schedule.'''
    solint = schedule[min(i, len(schedule) - 1)] if schedule else 'inf'
    return {'solint': solint, 'calmode': 'p', 'nsigma': Cleaner._nsigma_for_solint(solint)}

  def image_gen(self, options:Options):
    '''Generate an image: initial clean, then phase-only self-cal cycles down a
    shortening solint schedule (stopping early on convergence or divergence),
    then one guarded amp+phase pass. Cycles are scored by dynamic range and the
    best-scoring image is kept.

    Packages the results folder and fits the target on the winner. Records its
    filename base on options.best_image_base and returns the image_data.Image.
    '''
    fn = options.image_filename
    #optional test image: settle cell/imsize/robust before anything is scored
    Cleaner.test_image_cycle(options)
    #initial clean: the baseline the self-cal cycles must beat
    initial = image_data.Image(options, Cleaner.initial_cycle(options=options), base=fn)
    best = {'base': fn, 'dr': initial.dynamic_range(),
            'flux': initial.total_flux(), 'image': initial, 'cycle': 'initial'}
    run_log.cycle('initial', dynamic_range=best['dr'], decision='baseline to beat')

    if options.do_self_cal:
      peak = initial.peak()
      if peak is None or peak < MIN_FLUX_FOR_SELF_CAL or best['dr'] <= 0:
        #self-cal on a too-faint source (or a degenerate zero-RMS image) just solves
        #the noise -> skip it entirely
        measured = 'unmeasurable' if peak is None else f"{peak:.3g}"
        print(f"Peak {measured} Jy/beam < {MIN_FLUX_FOR_SELF_CAL} floor (or non-positive DR) "
              f"-> too faint to self-cal; keeping the initial image.")
        run_log.cycle('self-cal', decision=f"SKIPPED -- peak {measured} Jy/beam below the "
                                           f"{MIN_FLUX_FOR_SELF_CAL} Jy/beam floor")
      else:
        schedule = Cleaner._solint_schedule(options, max(0, options.self_cal_cycles))
        prev_dr = best['dr']
        diverged = False
        #carry the interactively-drawn mask forward: whatever was drawn on the initial
        #clean (or an imported options.mask) is reused each cycle -- loaded so it can be
        #refined, not redrawn from scratch every time.
        current_mask = Cleaner._mask_path(fn)
        #phase-only cycles: shorten solint as the model/SNR improves. Params come from
        #_propose_cycle_params per cycle, so an interactive mode can override them here.
        i = 0
        while i < len(schedule):
          params = Cleaner._propose_cycle_params(options, i, schedule)
          solint = params['solint']
          current = image_data.Image(options,
                                     Cleaner.self_cal_cycle(options, i, solint=solint,
                                                            calmode=params['calmode'],
                                                            mask=current_mask,
                                                            nsigma=params['nsigma']),
                                     base=f"{fn}_{i}")
          current_mask = Cleaner._mask_path(f"{fn}_{i}") or current_mask
          curr_dr = current.dynamic_range()
          if curr_dr <= 0:
            print(f"Self-cal cycle {i} (solint={solint}): non-positive dynamic range; stopping.")
            run_log.cycle(i, solint, 'p', curr_dr, decision='STOP -- non-positive dynamic range')
            diverged = True
            break
          improvement = ((curr_dr / prev_dr) * 100) - 100  #>0 DR rose (better); <0 diverging
          print(f"Self-cal cycle {i} (solint={solint}): DR {prev_dr:.1f} -> {curr_dr:.1f} "
                f"({improvement:+.1f}%)")

          #keep-best: adopt this cycle only if it genuinely raised the dynamic range
          adopted = curr_dr > best['dr']
          if adopted:
            best = {'base': f"{fn}_{i}", 'dr': curr_dr, 'flux': current.total_flux(),
                    'image': current, 'cycle': i}

          if improvement < 0:
            print("  DR dropped -> self-cal diverging; stopping, keeping best so far.")
            run_log.cycle(i, solint, 'p', curr_dr, improvement,
                          'STOP -- diverging (DR dropped); keeping the best so far')
            diverged = True
            break
          if improvement < SELF_CAL_MIN_IMPROVEMENT_PCT:
            print(f"  improvement < {SELF_CAL_MIN_IMPROVEMENT_PCT}% -> converged; stopping.")
            run_log.cycle(i, solint, 'p', curr_dr, improvement,
                          f"STOP -- converged (gain below {SELF_CAL_MIN_IMPROVEMENT_PCT}%)"
                          + ('; new best' if adopted else ''))
            break
          run_log.cycle(i, solint, 'p', curr_dr, improvement,
                        'new best' if adopted else 'kept previous best')
          prev_dr = curr_dr
          i += 1

        #final amplitude+phase pass -- only after a healthy phase run (not a divergent
        #one, whose corrected data/model are already suspect). Guarded so it's kept
        #only if it raises DR without scaling the source flux away.
        if SELF_CAL_FINAL_AP and schedule and not diverged:
          ap_idx = len(schedule)
          #default depth, not _nsigma_for_solint: solint is 'inf' here but the model is
          #at its best by now, so this pass cleans deep rather than shallow.
          ap = image_data.Image(options,
                                Cleaner.self_cal_cycle(options, ap_idx, solint='inf', calmode='ap', mask=current_mask),
                                base=f"{fn}_{ap_idx}")
          current_mask = Cleaner._mask_path(f"{fn}_{ap_idx}") or current_mask
          ap_dr = ap.dynamic_range()
          ap_flux = ap.total_flux()
          flux_loss = (1 - ap_flux / best['flux']) * 100 if best['flux'] and ap_flux else 0.0
          print(f"Final a&p pass: DR {best['dr']:.1f} -> {ap_dr:.1f}, flux change {-flux_loss:+.1f}%")
          if ap_dr > best['dr'] and flux_loss <= SELF_CAL_AP_MAX_FLUX_LOSS_PCT:
            best = {'base': f"{fn}_{ap_idx}", 'dr': ap_dr, 'flux': ap_flux,
                    'image': ap, 'cycle': f"{ap_idx} (a&p)"}
            print("  adopted a&p pass.")
            run_log.cycle('a&p', 'inf', 'ap', ap_dr, -flux_loss,
                          'ADOPTED -- raised DR without losing flux')
          else:
            reason = ("no DR gain" if ap_dr <= best['dr']
                      else f"flux loss {flux_loss:.1f}% > {SELF_CAL_AP_MAX_FLUX_LOSS_PCT}%")
            print(f"  rejected a&p pass ({reason}); keeping best phase image.")
            run_log.cycle('a&p', 'inf', 'ap', ap_dr, -flux_loss,
                          f"REJECTED ({reason}); kept the best phase image")

        #optional final baseline-cal (blcal) polish ('baseline_cal' breakpoint),
        #and only on a bright source (blcal's ~N^2/2 params overfit faint/extended flux).
        #Guarded exactly like the a&p pass: kept only if it raises DR without losing flux.
        if options.decision('baseline_cal') != OFF and not diverged:
          peak = best['image'].peak()
          if peak is None or peak < MIN_FLUX_FOR_BASELINE_CAL:
            measured = 'unmeasurable' if peak is None else f"{peak:.3g}"
            print(f"Baseline cal skipped: peak {measured} Jy/beam < "
                  f"{MIN_FLUX_FOR_BASELINE_CAL} floor (too faint for per-baseline solve).")
            run_log.cycle('blcal', decision=f"SKIPPED -- peak {measured} Jy/beam below the "
                                            f"{MIN_FLUX_FOR_BASELINE_CAL} Jy/beam floor")
          else:
            bl = image_data.Image(options,
                                  Cleaner.baseline_cal_cycle(options, 'blcal', mask=current_mask),
                                  base=f"{fn}_blcal")
            bl_dr = bl.dynamic_range()
            bl_flux = bl.total_flux()
            bl_flux_loss = (1 - bl_flux / best['flux']) * 100 if best['flux'] and bl_flux else 0.0
            print(f"Baseline cal (blcal): DR {best['dr']:.1f} -> {bl_dr:.1f}, "
                  f"flux change {-bl_flux_loss:+.1f}%")
            if bl_dr > best['dr'] and bl_flux_loss <= SELF_CAL_AP_MAX_FLUX_LOSS_PCT:
              best = {'base': f"{fn}_blcal", 'dr': bl_dr, 'flux': bl_flux,
                      'image': bl, 'cycle': 'blcal'}
              print("  adopted baseline cal.")
              run_log.cycle('blcal', '-', 'blcal', bl_dr, -bl_flux_loss,
                            'ADOPTED -- raised DR without losing flux')
            else:
              reason = ("no DR gain" if bl_dr <= best['dr']
                        else f"flux loss {bl_flux_loss:.1f}% > {SELF_CAL_AP_MAX_FLUX_LOSS_PCT}%")
              print(f"  rejected baseline cal ({reason}); keeping best image.")
              run_log.cycle('blcal', '-', 'blcal', bl_dr, -bl_flux_loss,
                            f"REJECTED ({reason}); kept the best image")

    options.best_image_base = best['base']
    print(f"Best image: {best['base']} (cycle {best['cycle']}, DR {best['dr']:.1f})")
    run_log.event(f"best image: {best['base']} (cycle {best['cycle']}, DR {best['dr']:.1f})")
    #gather the final products (FITS, pbcor, listobs, log) into a results folder;
    #optional core subtraction -- a separate product (the jet image), not a candidate
    #for best: it is a different source, so its dynamic range is not comparable.
    try:
      Cleaner.core_subtract_cycle(options, best['image'])
    except Exception as e:
      print(f"Core subtraction failed (image still available at {best['base']}): {e}")
    #best-effort so a packaging hiccup never loses a completed image
    try:
      Cleaner.collect_results(options)
    except Exception as e:
      print(f"Results collection failed (image still available at {best['base']}): {e}")
    #2D Gaussian fit of the target on the best image -> <name>.fit.json in the results
    #folder. Guarded separately from collect_results: a fit that can't be made must not
    #cost us the packaged products, and neither can cost us the image.
    try:
      source_fit.fit_best_image(options, best['image'])
    except Exception as e:
      print(f"Source fit failed (image still available at {best['base']}): {e}")
    return best['image']
    #for each in images:
    #  pprint.pp(f"{each.__dict__}")

  @staticmethod
  def collect_results(options:Options):
    '''Copy the run's products into one <proj>_<source>_<band>_results/ folder,
    so they aren't scattered across measurement_sets/ and the repo root:

        <name>.fits, <name>.pbcor.tt0, <name>.png, <name>.mask,
        <name>-listobs.txt, casa.log

    Sets options.results_name, off which source_fit then names <name>.fit.json,
    <name>.imfit.log and <name>.imfit.residual into the same folder.

    Products are copied, not moved, so measurement_sets/ stays intact for
    re-runs. Best-effort: any one item failing is reported, not fatal.'''
    proj = getattr(options.observation_data.obs_info, 'project', '') or options.proj_code or 'run'
    name = f"{proj}_{options.source_ids.name}_{options.band}"
    results_dir = Path(f"{name}_results")
    results_dir.mkdir(parents=True, exist_ok=True)
    options.results_dir = str(results_dir)  #so main() can drop replay.py here
    options.results_name = name            #so source_fit names its record to match
    base = options.best_image_base  #measurement_sets/<proj>_<source>_<band>[_<cycle>]

    #1) FITS export of the best restored (flat-noise) image.
    restored = image_data.restored_image(base)
    if not restored:
      print(f"results: no restored image found for {base}; skipping FITS export.")
    else:
      try:
        ct.exportfits(imagename=restored,
                      fitsimage=str(results_dir / f"{name}.fits"), overwrite=True)
      except Exception as e:
        print(f"results: FITS export failed ({restored}): {e}")

    #2) primary-beam-corrected image (impbcor writes <base>.pbcorimage) -> copy the
    #   CASA image directory into the folder under a .pbcor.tt0 name.
    pbcor = base + '.pbcorimage'
    if Path(pbcor).is_dir():
      Cleaner._copy_tree_into(pbcor, results_dir / f"{name}.pbcor.tt0")
    else:
      print(f"results: no pbcor image found ({pbcor}).")

    #3) PNG preview of the best image (export_png writes <base>.png)
    png = base + '.png'
    if Path(png).is_file():
      shutil.copy2(png, results_dir / f"{name}.png")
    else:
      print(f"results: no PNG found ({png}).")

    #3b) clean mask (the interactively-drawn regions). Save it and point options.mask at
    #    this durable copy so it round-trips into import.json -> --import can replay the
    #    regions non-interactively (the pixel mask itself is far too big to embed in JSON).
    mask = base + '.mask'
    if Path(mask).is_dir():
      mask_dest = results_dir / f"{name}.mask"
      Cleaner._copy_tree_into(mask, mask_dest)
      options.mask = str(mask_dest)
      print(f"results: saved clean mask -> {mask_dest} (import.json will reference it)")

    #3c) core-subtracted (jet) image, when core subtraction ran: FITS + pbcor + PNG,
    #    named .coresub so it never collides with the main image's products
    if coresub := getattr(options, 'coresub_base', ''):
      restored_jet = image_data.restored_image(coresub)
      if restored_jet:
        try:
          ct.exportfits(imagename=restored_jet,
                        fitsimage=str(results_dir / f"{name}.coresub.fits"), overwrite=True)
        except Exception as e:
          print(f"results: coresub FITS export failed ({restored_jet}): {e}")
      if Path(coresub + '.pbcorimage').is_dir():
        Cleaner._copy_tree_into(coresub + '.pbcorimage', results_dir / f"{name}.coresub.pbcor.tt0")
      if Path(coresub + '.png').is_file():
        shutil.copy2(coresub + '.png', results_dir / f"{name}.coresub.png")

    #4) target listobs (log_listobs writes <calibrated_filename>-listobs.txt)
    listobs = options.calibrated_filename + '-listobs.txt'
    if Path(listobs).is_file():
      shutil.copy2(listobs, results_dir / f"{name}-listobs.txt")
    else:
      print(f"results: no listobs found ({listobs}).")

    #5) this run's CASA log
    try:
      logpath = ct.casalog.logfile()
      if logpath and Path(logpath).is_file():
        shutil.copy2(logpath, results_dir / 'casa.log')
    except Exception as e:
      print(f"results: could not copy CASA log: {e}")

    print(f"Results collected in {results_dir}/")
    return results_dir

  @staticmethod
  def _copy_tree_into(src, dest):
    '''Copy a CASA image directory to dest, replacing any existing copy.'''
    dest = Path(dest)
    if dest.exists():
      shutil.rmtree(dest)
    shutil.copytree(src, dest)

  @staticmethod
  def find_solint_variations(options:Options):
    '''
    define different solints for self cal cycles, and run cycles with those solints to find the best one 
    '''
    obs_solint = options.solint
    

  @staticmethod
  def manual_clean_calibration(options:Options):
    '''
    for doing manual calibration while also manual cleaning 
    '''
    print(f"Starting casa shell (logging to {ct.casalog.logfile()})")
    #no --logfile: start_casa runs in THIS process and would repoint the process-wide
    #logger, splitting the run's log before collect_results copies it.
    casashell.start_casa([])

  @staticmethod
  def export_png(image_base, outfile=None):
    '''Render the restored tclean image to a PNG via casaviewer, run under a
    headless virtual X display (Xvfb) so no real monitor / $DISPLAY is needed and
    it can't hang on "waiting for viewer process". Best-effort -- any failure is
    logged but never breaks the imaging pipeline.

    Requires the Xvfb binary (system package 'xvfb') and the 'xvfbwrapper' python
    package (in requirements.txt).
    '''
    image = image_data.restored_image(image_base)
    if not image:
      print(f"PNG export skipped: no restored image found for {image_base}")
      return None
    outfile = outfile or (image_base + '.png')
    try:
      import io, contextlib
      from xvfbwrapper import Xvfb
      import casaviewer
      #Xvfb sets $DISPLAY for casaviewer's spawned viewer subprocess, then tears down
      with Xvfb():
        #casaviewer is chatty on stdout ("(N) waiting for viewer process...") -- swallow it
        with contextlib.redirect_stdout(io.StringIO()):
          casaviewer.imview(raster={'file': image, 'colorwedge': True}, out=outfile)
          #Shut the persistent viewer process down while $DISPLAY is still alive, so it
          #closes its own X11 connection cleanly instead of printing "The X11 connection
          #broke (error 1)" when the `with Xvfb()` block tears the display down underneath it.
          Cleaner._shutdown_casaviewer()
      print(f"Wrote image PNG: {outfile}")
    except Exception as e:
      print(f"PNG export failed ({image}): {e}")
      return None
    return outfile

  @staticmethod
  def _shutdown_casaviewer():
    '''Stop the persistent viewer subprocess imview() spawns and caches.

    PNGs render under a short-lived Xvfb display, so a viewer still running when
    that display is torn down prints "The X11 connection broke (error 1)". Called
    while $DISPLAY is up, this shuts the viewer down cleanly, deregisters it,
    kills any leftover process and clears viewertool's caches, so the next
    export_png() launches a fresh viewer instead of pinging a dead one.

    Best-effort: reaches into casaviewer's private state, so failures are ignored.'''
    try:
      from casaviewer.private import viewertool as vt
    except Exception:
      return
    vdict = vt.__dict__
    #ask each live viewer to shut itself down (casaviewer's own graceful shutdown)
    try:
      vdict['__shutdown_sans_casatools']()
    except Exception:
      pass
    #drop the now-dead viewer(s) from the casatools registry so a relaunch can't
    #rediscover a stale URI
    try:
      from casatools import ctsys
      for uri in (vdict.get('__uri') or {}).values():
        if uri:
          try: ctsys.remove_service(uri)
          except Exception: pass
    except Exception:
      pass
    #make sure the subprocess is really gone
    for proc in (vdict.get('__proc') or {}).values():
      if proc is not None:
        try: proc.kill()
        except Exception: pass
    #reset viewertool's per-server caches -> next call goes straight to a clean launch
    for cache_name in ('__proc', '__uri', '__stub', '__channel', '__stub_id'):
      cache = vdict.get(cache_name)
      if isinstance(cache, dict):
        for key in cache:
          cache[key] = None

  #Map a VLA config letter to its column in the BAND_* resolution tables (A/B/C/D).
  CONFIG_INDEX = {'A': 0, 'B': 1, 'C': 2, 'D': 3}

  @staticmethod
  def find_cell_size(options:Options):
    '''Return the tclean cell size as a clean '<N>arcsec' string. Uses the custom
    value if set, else 1/10th of the band's angular resolution for the array config.'''
    if options.use_custom_cell_size:
      cell = options.cell_size
    else:
      cell = BAND_ANGULAR_RESOLUTION[options.band][Cleaner._config_index(options)] / 10
    return Cleaner._as_arcsec(cell)

  @staticmethod
  def _config_index(options:Options):
    '''Column index (A/B/C/D) into the BAND_* config tables for this observation.

    Prefers the config derived from the MS antenna layout (works for any VLA MS,
    manual or radio_search); falls back to a config letter already on options,
    then to the ARRAY_CONFIGURATION default. Hybrid configs (e.g. 'BnA') resolve
    by their leading letter.'''
    derived = parse.vla_config_from_antennas(
      getattr(options.observation_data, 'antennas', None))
    letter = (derived or options.array_config or '').strip().upper()[:1]
    idx = Cleaner.CONFIG_INDEX.get(letter, ARRAY_CONFIGURATION)
    if letter not in Cleaner.CONFIG_INDEX:
      print(f"find_cell_size: could not determine array config "
            f"(derived={derived!r}, options={options.array_config!r}); "
            f"using default index {ARRAY_CONFIGURATION}.")
    return idx

  @staticmethod
  def _as_arcsec(value):
    '''Normalize a cell size (number, '0.03', or '0.03arcsec') to exactly one
    'arcsec' suffix -- prevents the '0.03arcsecarcsec' double-suffix tclean error.'''
    s = str(value).strip()
    while s.endswith('arcsec'):
      s = s[:-len('arcsec')].strip()
    return f"{s}arcsec"

  @staticmethod
  def _arcsec_value(value) -> float:
    '''Parse a cell size (number, '0.03', or '0.03arcsec') to a float in arcsec.
    Returns 0.0 if it can't be parsed.'''
    s = str(value).strip().lower()
    while s.endswith('arcsec'):
      s = s[:-len('arcsec')].strip()
    try:
      return float(s)
    except ValueError:
      return 0.0

  @staticmethod
  def _multiscale_scales(options:Options) -> list[int]:
    '''tclean `scales` (in pixels) for scale-sensitive deconvolvers.

    Builds a point-source term (0) plus a beam-based ladder (MULTISCALE_BEAM_MULTIPLIERS
    x the synthesized beam, in pixels). The largest scale is capped by the band/config
    Largest Angular Scale (BAND_LARGEST_SCALE)'''
    if options.deconvolver not in ('multiscale', 'mtmfs'):
      return []
    if options.band not in BAND_ANGULAR_RESOLUTION or options.band not in BAND_LARGEST_SCALE:
      return []  #band not resolved to a table entry (e.g. still 'auto') -> single-scale
    cell = Cleaner._arcsec_value(options.cell_size)
    if cell <= 0:
      return []
    idx = Cleaner._config_index(options)
    beam_px = BAND_ANGULAR_RESOLUTION[options.band][idx] / cell
    las_px = BAND_LARGEST_SCALE[options.band][idx] / cell
    size_cap = 0.45 * min(options.image_size)  #keep the largest scale inside the field
    cap = min(las_px, size_cap)
    scales = {0}
    for mult in MULTISCALE_BEAM_MULTIPLIERS:
      px = round(mult * beam_px)
      if 0 < px <= cap:
        scales.add(px)
    return sorted(scales)

