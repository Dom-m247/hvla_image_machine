import casatasks as ct

from ..data_class import data
from ..constants import *

def amp_cal_split(options):
  '''
  split off amp and target(?) fields for calibration
  #split(vis =  msfile+".ms", outputvis = "init.ms", datacolumn = 'data', field = (source_id, ampcal_id), spw = used_spws)
  '''
  
  ct.split(vis=FULLMS+'.ms',outputvis=AMP_CAL_MS+'.ms',datacolumn = 'data', field=())