from classes import image_data
from pre_calibration.options_class import Options
from classes.constants import *
from data_calibration import main_calibrations
from data_calibration import parse_listobs as parse
from typing import Any
from pathlib import Path
import casatasks as ct
import casashell
import pprint
import shutil
from classes.Loading_Animation import *
#I(this script) am so FULL of magic numbers 🥰 that are absolutley pulled from thin Air 

class Cleaner:
  @staticmethod
  def _mask_kwargs(options:Options, mask=None) -> dict[str, Any]:
    '''tclean masking/stop params for the self-cal cleans. Precedence:

      1. a saved/carried mask (the `mask` arg, else options.mask) that exists on disk
         -> usemask='user' with that mask. Reproduces previously-drawn regions; works
         with interactive imaging ON (loaded so you refine, not redraw) or OFF (a
         hands-free replay, e.g. from --import).
      2. interactive imaging -> the user draws the mask (nsigma just stops).
      3. automatic imaging   -> CASA auto-multithresh builds the mask.

    nsigma stops cleaning at the noise floor in every case (the model this clean
    writes feeds the next gaincal, so noise in the model corrupts the solution).
    '''
    kw: dict[str, Any] = {'nsigma': SELF_CAL_NSIGMA}
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
  def _dynamic_range(image):
    '''Self-cal figure of merit: peak / background RMS. 0.0 if RMS is non-positive.
    (Whole-image RMS is contaminated by the source, but as a relative cycle-to-cycle
    score that is fine -- as self-cal improves, the peak rises and sidelobes drop,
    so DR rises. An off-source RMS box would be more rigorous; noted for later.)'''
    rms = image.rms[0]
    return image.max[0] / rms if rms > 0 else 0.0

  @staticmethod
  def initial_cycle(options:Options,
                   imagename='first_imamge',
                   vis = CALIBRATED_MS+'.ms',
                   deconvolver = 'mtmfs',
                   small_scale_bias=0.7,# a thing that should be able to change as an imput?
                   weighting='briggs',
                   robust=0.5,
                   interactive=False, #pick at GUI/Import!
                   niter=9999, #vibes?
                   savemodel='modelcolumn',
                   nterms=1,  #jvla = 2, HVLA = 1
                   scales = [],
                   imsize=DEFAULT_IMAGE_SIZE
    ):
    '''
    The initial Clean of 
    '''
    options.cell_size = Cleaner.find_cell_size(options)
    #Only when self-cal is selected: use a shallow, mode-aware-masked clean so the
    #model handed to the first gaincal is clean flux, not noise (nsigma stop +
    #auto-multithresh when automatic; niter is the safety cap). With self-cal off,
    #leave the plain final-image clean exactly as it was.
    mask_kwargs = {}
    if options.do_self_cal:
      niter = 1000
      mask_kwargs = Cleaner._mask_kwargs(options)
    elif getattr(options, 'mask', ''):
      #no self-cal, but a saved mask was supplied (e.g. --import replay) -> honor it
      mask_kwargs = Cleaner._mask_kwargs(options)
    #add nmajor=1/2 instead of lowering niter?
    ct.tclean(imagename=options.image_filename,
                  vis=options.calibrated_filename+'.ms',
                  deconvolver=options.deconvolver,
                  smallscalebias=small_scale_bias,
                  weighting=options.weighting,
                  robust=robust,
                  interactive=options.interactive_image,
                  niter=niter,
                  savemodel=savemodel,
                  nterms=nterms,
                  scales=Cleaner._multiscale_scales(options),
                  cell=options.cell_size,
                  imsize=options.image_size,
                  pblimit=-0.1,
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
  def _clean_and_measure(options:Options, label, mask=None):
    '''Clean the (re-calibrated) source MS into <image_filename>_<label>, pbcor + PNG
    it, and return imstat on the flat-noise restored image. Shared by the self-cal and
    baseline-cal cycles so they image identically (same mask/scales/weighting).

    `mask`: a saved/carried mask to reuse for this clean (see _mask_kwargs).'''
    name = options.image_filename + '_' + str(label)
    x = ct.tclean(imagename=name,
                  vis=options.calibrated_filename+'.ms',
                  deconvolver=options.deconvolver,
                  smallscalebias=0.7,
                  weighting=options.weighting,
                  robust=0.5,
                  interactive=options.interactive_image,
                  niter=9999,  #safety cap; nsigma (in _mask_kwargs) is the real stopping point
                  savemodel='modelcolumn',
                  nterms=1,  #jvla = 2, HVLA = 1
                  scales=Cleaner._multiscale_scales(options),
                  cell=options.cell_size,
                  imsize=options.image_size,
                  pblimit=-0.01,
                  **Cleaner._mask_kwargs(options, mask)
    )
    ct.impbcor(imagename=name+'.image.tt0', pbimage=name+'.pb.tt0',
               outfile=name+'.pbcorimage', overwrite=True)
    Cleaner.export_png(name)
    pprint.pp(x)
    #flat-noise restored image for a consistent, uniform-noise RMS (see initial_cycle)
    return ct.imstat(imagename=name+'.image.tt0')

  @staticmethod
  def self_cal_cycle(options:Options,iter,solint='inf',calmode='p',mask=None):
    '''
    Runs a single automated cycle of self calibration.

    solint : gaincal solution interval for this cycle (loop shortens it as SNR builds).
    calmode: 'p' for phase-only cycles, 'ap' for the final amplitude+phase pass.
    mask   : a saved/carried clean mask to reuse (so interactive users draw once).
    '''
    iter = str(iter)
    #calibration cycle -- model column feeding gaincal comes from the previous clean
    LoadingAnimation.performing_action(action=f'self-cal cylce {iter} (solint={solint}, calmode={calmode})',
                                       target=main_calibrations.self_cal_cycle,
                                       args=(options,iter,solint,calmode))
    return Cleaner._clean_and_measure(options, iter, mask=mask)

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
    return sched

  def image_gen(self, options:Options):
    '''
    Handle generating an image. Runs the initial clean, then phase-only self-cal
    cycles that step through a shortening solint schedule (SELF_CAL_SOLINTS, capped
    by options.self_cal_cycles), stopping early on convergence or divergence, then
    one guarded amplitude+phase pass. Cycles are scored by dynamic range (peak/RMS)
    and the best-scoring image is kept.

    Records the best image's filename base on options.best_image_base and returns
    the best image_data.Image.
    '''
    fn = options.image_filename
    #initial clean: the baseline the self-cal cycles must beat
    initial = image_data.Image(options, Cleaner.initial_cycle(options=options))
    best = {'base': fn, 'dr': Cleaner._dynamic_range(initial),
            'flux': initial.flux[0], 'image': initial, 'cycle': 'initial'}

    if options.do_self_cal:
      peak = initial.max[0]
      if peak < MIN_FLUX_FOR_SELF_CAL or best['dr'] <= 0:
        #self-cal on a too-faint source (or a degenerate zero-RMS image) just solves
        #the noise -> skip it entirely
        print(f"Peak {peak:.3g} Jy/beam < {MIN_FLUX_FOR_SELF_CAL} floor (or non-positive DR) "
              f"-> too faint to self-cal; keeping the initial image.")
      else:
        schedule = Cleaner._solint_schedule(options, max(0, options.self_cal_cycles))
        prev_dr = best['dr']
        diverged = False
        #carry the interactively-drawn mask forward: whatever was drawn on the initial
        #clean (or an imported options.mask) is reused each cycle -- loaded so it can be
        #refined, not redrawn from scratch every time.
        current_mask = Cleaner._mask_path(fn)
        #phase-only cycles: shorten solint as the model/SNR improves
        for i, solint in enumerate(schedule):
          current = image_data.Image(options,
                                     Cleaner.self_cal_cycle(options, i, solint=solint, calmode='p', mask=current_mask))
          current_mask = Cleaner._mask_path(f"{fn}_{i}") or current_mask
          curr_dr = Cleaner._dynamic_range(current)
          if curr_dr <= 0:
            print(f"Self-cal cycle {i} (solint={solint}): non-positive dynamic range; stopping.")
            diverged = True
            break
          improvement = ((curr_dr / prev_dr) * 100) - 100  #>0 DR rose (better); <0 diverging
          print(f"Self-cal cycle {i} (solint={solint}): DR {prev_dr:.1f} -> {curr_dr:.1f} "
                f"({improvement:+.1f}%)")

          #keep-best: adopt this cycle only if it genuinely raised the dynamic range
          if curr_dr > best['dr']:
            best = {'base': f"{fn}_{i}", 'dr': curr_dr, 'flux': current.flux[0],
                    'image': current, 'cycle': i}

          if improvement < 0:
            print("  DR dropped -> self-cal diverging; stopping, keeping best so far.")
            diverged = True
            break
          if improvement < SELF_CAL_MIN_IMPROVEMENT_PCT:
            print(f"  improvement < {SELF_CAL_MIN_IMPROVEMENT_PCT}% -> converged; stopping.")
            break
          prev_dr = curr_dr

        #final amplitude+phase pass -- only after a healthy phase run (not a divergent
        #one, whose corrected data/model are already suspect). Guarded so it's kept
        #only if it raises DR without scaling the source flux away.
        if SELF_CAL_FINAL_AP and schedule and not diverged:
          ap_idx = len(schedule)
          ap = image_data.Image(options,
                                Cleaner.self_cal_cycle(options, ap_idx, solint='inf', calmode='ap', mask=current_mask))
          current_mask = Cleaner._mask_path(f"{fn}_{ap_idx}") or current_mask
          ap_dr = Cleaner._dynamic_range(ap)
          flux_loss = (1 - ap.flux[0] / best['flux']) * 100 if best['flux'] else 0.0
          print(f"Final a&p pass: DR {best['dr']:.1f} -> {ap_dr:.1f}, flux change {-flux_loss:+.1f}%")
          if ap_dr > best['dr'] and flux_loss <= SELF_CAL_AP_MAX_FLUX_LOSS_PCT:
            best = {'base': f"{fn}_{ap_idx}", 'dr': ap_dr, 'flux': ap.flux[0],
                    'image': ap, 'cycle': f"{ap_idx} (a&p)"}
            print("  adopted a&p pass.")
          else:
            reason = ("no DR gain" if ap_dr <= best['dr']
                      else f"flux loss {flux_loss:.1f}% > {SELF_CAL_AP_MAX_FLUX_LOSS_PCT}%")
            print(f"  rejected a&p pass ({reason}); keeping best phase image.")

        #optional final baseline-cal (blcal) polish -- opt-in ('baseline_cal' breakpoint),
        #and only on a bright source (blcal's ~N^2/2 params overfit faint/extended flux).
        #Guarded exactly like the a&p pass: kept only if it raises DR without losing flux.
        if 'baseline_cal' in options.breakpoints and not diverged:
          peak = best['image'].max[0]
          if peak < MIN_FLUX_FOR_BASELINE_CAL:
            print(f"Baseline cal skipped: peak {peak:.3g} Jy/beam < "
                  f"{MIN_FLUX_FOR_BASELINE_CAL} floor (too faint for per-baseline solve).")
          else:
            bl = image_data.Image(options, Cleaner.baseline_cal_cycle(options, 'blcal', mask=current_mask))
            bl_dr = Cleaner._dynamic_range(bl)
            bl_flux_loss = (1 - bl.flux[0] / best['flux']) * 100 if best['flux'] else 0.0
            print(f"Baseline cal (blcal): DR {best['dr']:.1f} -> {bl_dr:.1f}, "
                  f"flux change {-bl_flux_loss:+.1f}%")
            if bl_dr > best['dr'] and bl_flux_loss <= SELF_CAL_AP_MAX_FLUX_LOSS_PCT:
              best = {'base': f"{fn}_blcal", 'dr': bl_dr, 'flux': bl.flux[0],
                      'image': bl, 'cycle': 'blcal'}
              print("  adopted baseline cal.")
            else:
              reason = ("no DR gain" if bl_dr <= best['dr']
                        else f"flux loss {bl_flux_loss:.1f}% > {SELF_CAL_AP_MAX_FLUX_LOSS_PCT}%")
              print(f"  rejected baseline cal ({reason}); keeping best image.")

    options.best_image_base = best['base']
    print(f"Best image: {best['base']} (cycle {best['cycle']}, DR {best['dr']:.1f})")
    #gather the final products (FITS, pbcor, listobs, log) into a results folder;
    #best-effort so a packaging hiccup never loses a completed image
    try:
      Cleaner.collect_results(options)
    except Exception as e:
      print(f"Results collection failed (image still available at {best['base']}): {e}")
    return best['image']
    #for each in images:
    #  pprint.pp(f"{each.__dict__}")

  @staticmethod
  def collect_results(options:Options):
    '''Copy the final products of a run into one uniquely-named results folder in
    the working directory, so they aren't scattered across measurement_sets/ and the
    repo root:

        <proj>_<source>_<band>_results/
            <proj>_<source>_<band>.fits          FITS of the best restored image (.image.tt0)
            <proj>_<source>_<band>.pbcor.tt0     primary-beam-corrected image (CASA image)
            <proj>_<source>_<band>.png           PNG preview of the best image
            <proj>_<source>_<band>.mask          clean mask (drawn regions), if any
            <proj>_<source>_<band>-listobs.txt   target listobs
            casa.log                             copy of this run's CASA log

    Products are copied (not moved), so measurement_sets/ stays intact for re-runs.
    Best-effort: any one item failing is reported, not fatal.'''
    proj = getattr(options.observation_data.obs_info, 'project', '') or options.proj_code or 'run'
    name = f"{proj}_{options.source_ids.name}_{options.band}"
    results_dir = Path(f"{name}_results")
    results_dir.mkdir(parents=True, exist_ok=True)
    options.results_dir = str(results_dir)  #so main() can drop replay.py here
    base = options.best_image_base  #measurement_sets/<proj>_<source>_<band>[_<cycle>]

    #1) FITS export of the best restored (flat-noise) image. mtmfs writes .image.tt0;
    #   other deconvolvers write .image.
    restored = next((base + ext for ext in ('.image.tt0', '.image')
                     if Path(base + ext).is_dir()), None)
    if restored is None:
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
    print(f"Starting casa shell")
    casalogFile = ct.casalog.logfile()
    print(f"{casalogFile}")
    print(f"----------------")
    casashell.start_casa('--logfile logfile.txt')  

  @staticmethod
  def export_png(image_base, outfile=None):
    '''Render the restored tclean image to a PNG via casaviewer, run under a
    headless virtual X display (Xvfb) so no real monitor / $DISPLAY is needed and
    it can't hang on "waiting for viewer process". Best-effort -- any failure is
    logged but never breaks the imaging pipeline.

    Requires the Xvfb binary (system package 'xvfb') and the 'xvfbwrapper' python
    package (in requirements.txt).

    mtmfs/nterms writes <name>.image.tt0; other deconvolvers write <name>.image.
    '''
    import os
    image = next((image_base + ext for ext in ('.image.tt0', '.image')
                  if os.path.isdir(image_base + ext)), None)
    if image is None:
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
    '''Gracefully stop the persistent casaviewer viewer subprocess that imview()
    spawns and caches for reuse (it otherwise lingers until interpreter exit).

    We render each PNG under a short-lived Xvfb display, so a viewer left running
    when the display is torn down prints "The X11 connection broke (error 1)".
    Calling this while $DISPLAY is still up asks the viewer to shut itself down
    (graceful gRPC shutdown -> clean X11 close), removes it from the casatools
    service registry, kills any leftover process, and clears viewertool's caches
    so the next export_png() launches a fresh viewer instead of pinging a dead one.

    Best-effort: reaches into casaviewer's private state, so any failure is ignored.'''
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
    Largest Angular Scale (BAND_LARGEST_SCALE) -- cleaning structure bigger than the
    array ever measured just fits noise -- and by the image size so scales stay well
    inside the field. Returns [] for single-scale deconvolvers (which ignore `scales`),
    so selecting e.g. 'multiscale' actually cleans multi-scale instead of like a
    delta-function clean.'''
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

