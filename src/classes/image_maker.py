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
                   imsize=[1080,1080]
    ):
    cellsize = Cleaner.find_cell_size(options)
    ct.tclean(imagename=imagename,
                  vis=vis,
                  deconvolver=deconvolver,
                  smallscalebias=small_scale_bias,
                  weighting=weighting,
                  robust=robust,
                  interactive=interactive,
                  niter=niter,
                  savemodel=savemodel,
                  nterms=nterms,
                  scales=scales,
                  cell=(0.33/10),
                  imsize=imsize
                  )
  def gaincal_cycle(options:Options):
    pass
  def manual_clean(options):
    passing_ars = '--logfile' #+logfile
    casashell.start_casa('--logger')
    
  def find_cell_size(options:Options):
    '''returns 1/10th of the corresponding band's max angular freq'''
    if options.use_custom_cell_size:
      #options selected as True, 
      return options.cell_size
    angular_res = BAND_ANGULAR_RESOLUTION[options.band][ARRAY_CONFIGURATION]
    return (angular_res)/10

