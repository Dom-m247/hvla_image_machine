from classes import image_data
from pre_calibration.options_class import Options
from pre_calibration.constants import *
from data_calibration import main_calibrations
import casatasks as ct
import casashell
import pprint
from classes.terminal_helper import *
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
    return ct.imstat(imagename=options.image_filename+'.pbcorimage')
  
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
    pprint.pp(x)
    return ct.imstat(imagename=options.image_filename+'_'+iter+'.pbcorimage')
  

  def image_gen(self, options:Options):
    '''
    Handle generating an image!
    '''
    #initial cleaning,
    images = []
    
    images.append(image_data.Image(options,Cleaner.initial_cycle(options=options)))
    if options.do_self_cal:
      for iterations in range(options.self_cal_cycles):
        images.append(image_data.Image(options,Cleaner.self_cal_cycle(options,iterations)))
        print(f"{type(images[iterations].rms)} | {type(images[iterations+1].rms[0])}")
        improvment_score = ((images[iterations].rms[0] / images[iterations+1].rms[0]) * 100) - 100
        print(f"Image Improvment: Last image - {images[iterations].rms[0]} | current image {images[iterations+1].rms[0]}")
        print(f"That's an improvment of {improvment_score}%")
        if improvment_score < 10:
          print(f"Not meeting improvment requirment")
          #break
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

  def find_cell_size(options:Options):
    '''
    IF not specified returns 1/10th of the corresponding band's max angular freq
    '''
    if options.use_custom_cell_size:
      #options selected as True, 
      return options.cell_size
    angular_res = BAND_ANGULAR_RESOLUTION[options.band][ARRAY_CONFIGURATION]
    return (angular_res)/10

