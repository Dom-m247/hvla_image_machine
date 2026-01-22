from classes import *
from pre_calibration.options_class import Options
from pre_calibration.constants import *
import casatasks as ct
import casashell



class Cleaner:
  def tclean_cycle(options:Options,
                   imagename='first_im',
                   vis = CALIBRATED_MS+'.ms',
                   deconvolver = 'mtmfs',
                   small_scale_bias=0.7,# a thing that should be able to change as an imput?
                   weighting='briggs',
                   robust=0.5,
                   interactive=False, #pick at GUI/Import!
                   niter=9999,
                   savemodel='modelcolumn',
                   nterms=1,  #jvla = 2, HVLA = 1
                   scales = [],
                   imsize=DEFAULT_IMAGE_SIZE
    ):
    cellsize = Cleaner.find_cell_size(options)
    ct.tclean(imagename=options.image_filename,
                  vis=vis,
                  deconvolver=options.deconvolver,
                  smallscalebias=small_scale_bias,
                  weighting=options.weighting,
                  robust=robust,
                  interactive=options.interactive_image,
                  niter=niter,
                  savemodel=savemodel,
                  nterms=nterms,
                  scales=scales,
                  cell=str(cellsize)+'arcsec',
                  imsize=options.image_size,
                  #mask='circle[[800pix,800pix],600pix]'
                  )
  def cleaning_practice(options:Options):
    imagename='first_im',
    vis = CALIBRATED_MS+'.ms',
    deconvolver = 'mtmfs',
    small_scale_bias=0.7,# a thing that should be able to change as an imput?
    weighting='briggs',
    robust=0.5,
    interactive=False, #pick at GUI/Import!
    niter=9999,
    savemodel='modelcolumn',
    nterms=1,  #jvla = 2, HVLA = 1
    scales = [],
    imsize=DEFAULT_IMAGE_SIZE
    #tclean cycle 1
    print(f"clean cycle 1")
    ct.tclean(vis=CALIBRATED_MS+'.ms',imagename=options.image_filename+'_1',datacolumn='data',imsize=900,cell='0.033arcsec',pblimit=-0.1,gridder='standard',
              deconvolver='mtmfs',nterms=1,niter=1000,interactive=True,weighting='briggs',robust=0,savemodel='modelcolumn')
    print(f"calibration cycle 1")
    ct.gaincal(vis=CALIBRATED_MS+'.ms',caltable=GAINCAL_G2,solint='3s',refant='VA10',calmode='p',gaintype='G',minsnr=5)
    ct.applycal(vis=CALIBRATED_MS+'.ms',gaintable=GAINCAL_G2)
    print(f"clean cycle 2")
    x =ct.tclean(vis=CALIBRATED_MS+'.ms',imagename=options.image_filename+'_2',datacolumn='corrected',gridder='standard',cell='0.033arcsec',imsize=900,pblimit=-0.1,
              deconvolver='mtmfs',nterms=1,niter=100,interactive=True,weighting='briggs',robust=0,savemodel='none')
    return x

  def manual_clean(options:Options):
    '''
    for doing extra calibration while cleaning
    !NOT! interactive cleaning 
    '''
    print(f"Starting casa shell")
    casalogFile = ct.casalog.logfile()
    print(f"{casalogFile}")
    print(f"----------------")
    casashell.start_casa('--logfile logfile.txt')  

  def gain_cycle(options:Options,solint):
    pass
  def find_cell_size(options:Options):
    '''returns 1/10th of the corresponding band's max angular freq'''
    if options.use_custom_cell_size:
      #options selected as True, 
      return options.cell_size
    angular_res = BAND_ANGULAR_RESOLUTION[options.band][ARRAY_CONFIGURATION]
    return (angular_res)/10

