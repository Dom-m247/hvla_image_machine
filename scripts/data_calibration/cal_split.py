import casatasks as ct
import casaplotms
from . import parse_listobs as parse
from . import target_aquisition as TA
from ..data_class import data
from ..constants import *
import sys,pprint
from pathlib import Path

def get_command(options):
  TA.define_split_fields(options)
  TA.build_spwID(options)
  fields = options.get_dict_sp('split1_fields')
  spwID = options.get_dict_sp('spwIDs')
  return fields,spwID


def amp_cal_split(options):
  '''
  split off amp and target(?) fields for calibration
  #split(vis =  msfile+".ms", outputvis = "init.ms", datacolumn = 'data', field = (source_id, ampcal_id), spw = used_spws)
  '''
  if options.get_dict_sp('source') is None:
    TA.find_target(options)
  fields,spwID = get_command(options)
  if Path(sys.path[0]+("/"+AMP_CAL_MS+".ms")).is_dir():
    #raise Exception(f"{AMP_CAL_MS}.ms already exists, please move,delete, or rename it")
    pass #temp pass for development
  else:
    ct.split(vis=FULLMS+'.ms',outputvis=AMP_CAL_MS+'.ms',datacolumn = 'data', field=fields, spw=spwID)
  #if options.get_dict_sp('breakpoints')['verify_scans']:
    #pause, show listobs(vis='init.ms') and continue if correct, else END
  parse.log_listobs(AMP_CAL_MS)

  if "manual_flagging" in options.get_dict_sp('breakpoints'):
    print("Manual Data Flagging!")
    casaplotms.plotms(vis=(AMP_CAL_MS+".ms")) #doesn't work with wsl?
  
