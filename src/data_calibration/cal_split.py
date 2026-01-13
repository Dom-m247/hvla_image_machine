import casatasks as ct
import casaplotms
from . import parse_listobs as parse
from . import target_aquisition as TA
from classes.source_class import source_info
#from ..data_class import data
from pre_calibration.constants import *
import sys,pprint
from pathlib import Path

def get_command(options):
  fields = TA.define_split_fields(options)
  spwID = TA.build_spwID(options)
  return fields,spwID


def amp_cal_split(options):
  '''
  split off amp and target(?) fields for calibration
  #split(vis =  msfile+".ms", outputvis = "init.ms", datacolumn = 'data', field = (source_id, ampcal_id), spw = used_spws)
  '''
  if options.source is None:
    TA.find_target(options)
  else:
    TA.make_sourceID(options)
  fields,spwID = get_command(options)
  if Path(AMP_CAL_MS+".ms").is_dir():
    #raise Exception(f"{AMP_CAL_MS}.ms already exists, please move,delete, or rename it")
    ct.casalog.post(f"{FULLMS+'.ms'} -> {AMP_CAL_MS+'.ms'} | fields: {fields} | spw: {spwID}")
  else:
    ct.casalog.post(f"{FULLMS+'.ms'} -> {AMP_CAL_MS+'.ms'} | fields: {fields} | spw: {spwID}")
    ct.split(vis=FULLMS+'.ms',outputvis=AMP_CAL_MS+'.ms',datacolumn = 'data', field=fields, spw=spwID)
  #if options.get_dict_sp('breakpoints')['verify_scans']:
    #pause, show listobs(vis='init.ms') and continue if correct, else END
  parse.parseListObs.log_listobs(AMP_CAL_MS,options)

  if "manual_flagging" in options.breakpoints:
    print("Manual Data Flagging!")
    casaplotms.plotms(vis=(AMP_CAL_MS+".ms")) #doesn't work with wsl?
  
