from classes import *
from pre_calibration.options_class import Options
from pre_calibration.constants import *
from data_calibration import main_calibrations
import casatasks as ct
import casashell

#I(this script) am so FULL of magic numbers 🥰 that are absolutley pulled from thin Air 

class Cleaner:
  def initial_cycle(options:Options,
                   imagename='first_im',
                   vis = CALIBRATED_MS+'.ms',
                   deconvolver = 'mtmfs',
                   small_scale_bias=0.7,# a thing that should be able to change as an imput?
                   weighting='briggs',
                   robust=0.5,
                   interactive=False, #pick at GUI/Import!
                   niter=500, #vibes?
                   savemodel='modelcolumn',
                   nterms=1,  #jvla = 2, HVLA = 1
                   scales = [],
                   imsize=DEFAULT_IMAGE_SIZE
    ):
    '''
    The initial Clean of 
    '''
    options.cell_size = Cleaner.find_cell_size(options) 
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
                  #mask='circle[[800pix,800pix],600pix]'
                  )
    ct.impbcor(imagename=options.image_filename+'.image.tt0',pbimage=options.image_filename+'.pb.tt0',outfile=options.image_filename+'.pbcorimage')
    return ct.imstat(imagename=options.image_filename+'.pbcorimage')
  
  def self_cal_cycle(options:Options,iter):
    '''
    Runs a single automated cycle of self calibration
    '''
    vis = CALIBRATED_MS+'.ms',
    small_scale_bias=0.7, # a thing that should be able to change as an imput?
    robust=0.5,
    niter=9999,
    savemodel='modelcolumn',
    nterms=1,  #jvla = 2, HVLA = 1
    scales = [],
    #calibration cycle
    #ct.delmod(CALIBRATED_MS+'.ms') #not necessary to clean model after "inital" light clean 
    main_calibrations.self_cal_cycle(options)

    #clean
    ct.tclean(imagename=options.image_filename+'_'+iter,
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
    )
    ct.impbcor(imagename=options.image_filename+'_'+iter+'.image.tt0',
               pbimage=options.image_filename+'_'+iter+'.pb.tt0',
               outfile=options.image_filename+'_'+iter+'.pbcorimage',
               overwrite=True)
    return ct.imstat(imagename=options.image_filename+'_'+iter+'.pbcorimage')
  def manual_clean_calibration(options:Options):
    '''
    for doing manual calibration while also manual cleaning 
    '''
    print(f"Starting casa shell")
    casalogFile = ct.casalog.logfile()
    print(f"{casalogFile}")
    print(f"----------------")
    casashell.start_casa('--logfile logfile.txt')  

  def find_cell_size(options:Options):
    '''
    IF not specified returns 1/10th of the corresponding band's max angular freq
    '''
    if options.use_custom_cell_size:
      #options selected as True, 
      return options.cell_size
    angular_res = BAND_ANGULAR_RESOLUTION[options.band][ARRAY_CONFIGURATION]
    return (angular_res)/10

