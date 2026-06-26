from classes import image_data
from pre_calibration.options_class import Options
from classes.constants import *
from data_calibration import main_calibrations
import casatasks as ct
import casashell
import pprint
from classes.Loading_Animation import *
#I(this script) am so FULL of magic numbers 🥰 that are absolutley pulled from thin Air 

class Cleaner:
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
    if options.do_self_cal:
      niter = 1000 
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
                  scales=scales,
                  cell=options.cell_size,
                  imsize=options.image_size,
                  pblimit=-0.1
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
  def self_cal_cycle(options:Options,iter):#,solint):
    '''
    Runs a single automated cycle of self calibration
    '''
   
    small_scale_bias = 0.7 # a thing that should be able to change as an imput?
    robust= 0.5
    niter = 9999 
    savemodel='modelcolumn'
    nterms=1  #jvla = 2, HVLA = 1
    scales = []
    iter = str(iter)
    #calibration cycle
    #ct.delmod(CALIBRATED_MS+'.ms') #not necessary to clean model after "inital" light clean 
    #main_calibrations.self_cal_cycle(options,iter )
    LoadingAnimation.performing_action(action=f'self-cal cylce {iter}',
                                       target=main_calibrations.self_cal_cycle,
                                       args=(options,iter))#,solint))
    #clean
    x = ct.tclean(imagename=options.image_filename+'_'+iter,
                  vis=options.calibrated_filename+'.ms',
                  deconvolver=options.deconvolver,
                  smallscalebias=small_scale_bias,
                  weighting=options.weighting,
                  robust=robust,
                  interactive=options.interactive_image,
                  niter=niter,
                  savemodel=savemodel,
                  nterms=nterms,
                  scales=scales,
                  cell=options.cell_size,
                  imsize=options.image_size,
                  pblimit = -0.01
    )
    ct.impbcor(imagename=options.image_filename+'_'+iter+'.image.tt0',
               pbimage=options.image_filename+'_'+iter+'.pb.tt0',
               outfile=options.image_filename+'_'+iter+'.pbcorimage',
               overwrite=True)
    Cleaner.export_png(options.image_filename+'_'+iter)
    pprint.pp(x)
    #flat-noise restored image for a consistent, uniform-noise RMS (see initial_cycle)
    return ct.imstat(imagename=options.image_filename+'_'+iter+'.image.tt0')
  

  def image_gen(self, options:Options):
    '''
    Handle generating an image. Runs the initial clean, then self-cal cycles that
    stop early (on convergence OR divergence) and keep the best (lowest-RMS) image.

    Records the best image's filename base on options.best_image_base and returns
    the best image_data.Image.
    '''
    #initial clean: the baseline the self-cal cycles must beat
    initial = image_data.Image(options, Cleaner.initial_cycle(options=options))
    best = {'base': options.image_filename, 'rms': initial.rms[0],
            'image': initial, 'cycle': 'initial'}
    prev_rms = initial.rms[0]

    if options.do_self_cal:
      for iteration in range(options.self_cal_cycles):
        current = image_data.Image(options, Cleaner.self_cal_cycle(options, iteration))
        curr_rms = current.rms[0]
        if curr_rms <= 0:
          print(f"Self-cal cycle {iteration}: non-positive RMS ({curr_rms}); stopping.")
          break
        #improvement > 0 -> RMS dropped (better); < 0 -> RMS rose (diverging)
        improvement = ((prev_rms / curr_rms) * 100) - 100
        print(f"Self-cal cycle {iteration}: RMS {prev_rms:.3e} -> {curr_rms:.3e} ({improvement:+.1f}%)")

        #keep-best: adopt this cycle only if it genuinely lowered the RMS
        if curr_rms < best['rms']:
          best = {'base': f"{options.image_filename}_{iteration}", 'rms': curr_rms,
                  'image': current, 'cycle': iteration}

        #early stop
        if improvement < 0:
          print("  RMS increased -> self-cal diverging; stopping, keeping best so far.")
          break
        if improvement < SELF_CAL_MIN_IMPROVEMENT_PCT:
          print(f"  improvement < {SELF_CAL_MIN_IMPROVEMENT_PCT}% -> converged; stopping.")
          break
        prev_rms = curr_rms

    options.best_image_base = best['base']
    print(f"Best image: {best['base']} (cycle {best['cycle']}, RMS {best['rms']:.3e})")
    return best['image']
    #for each in images:
    #  pprint.pp(f"{each.__dict__}")

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

  @staticmethod
  def find_cell_size(options:Options):
    '''Return the tclean cell size as a clean '<N>arcsec' string. Uses the custom
    value if set, else 1/10th of the band's angular resolution for the array config.'''
    if options.use_custom_cell_size:
      cell = options.cell_size
    else:
      cell = BAND_ANGULAR_RESOLUTION[options.band][ARRAY_CONFIGURATION] / 10
    return Cleaner._as_arcsec(cell)

  @staticmethod
  def _as_arcsec(value):
    '''Normalize a cell size (number, '0.03', or '0.03arcsec') to exactly one
    'arcsec' suffix -- prevents the '0.03arcsecarcsec' double-suffix tclean error.'''
    s = str(value).strip()
    while s.endswith('arcsec'):
      s = s[:-len('arcsec')].strip()
    return f"{s}arcsec"

