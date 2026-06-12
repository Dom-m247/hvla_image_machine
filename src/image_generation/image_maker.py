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
                  cell=str(options.cell_size)+'arcsec',
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
                  cell=str(options.cell_size)+'arcsec',
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

  def find_solint_variations(options:Options):
    '''
    define different solints for self cal cycles, and run cycles with those solints to find the best one 
    '''
    obs_solint = options.solint
    

  def manual_clean_calibration(options:Options):
    '''
    for doing manual calibration while also manual cleaning 
    '''
    print(f"Starting casa shell")
    casalogFile = ct.casalog.logfile()
    print(f"{casalogFile}")
    print(f"----------------")
    casashell.start_casa('--logfile logfile.txt')  

  def export_png(image_base, outfile=None):
    '''Render the restored tclean image to a PNG. Best-effort: a failure here
    (e.g. no display) is logged but never breaks the imaging pipeline.

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
      import casaviewer
      casaviewer.imview(raster={'file': image, 'colorwedge': True}, out=outfile)
      print(f"Wrote image PNG: {outfile}")
    except Exception as e:
      print(f"PNG export failed ({image}): {e}")
      return None
    return outfile

  def find_cell_size(options:Options):
    '''
    IF not specified returns 1/10th of the corresponding band's max angular freq
    '''
    if options.use_custom_cell_size:
      #options selected as True, 
      return options.cell_size
    angular_res = BAND_ANGULAR_RESOLUTION[options.band][ARRAY_CONFIGURATION]
    return (angular_res)/10

