import casatasks as ct
import casaplotms
from . import parse_listobs as parse
from . import target_aquisition as TA
from classes.source_class import source_info
#from ..data_class import data
from classes.constants import *
from pre_calibration.options_class import Options

import sys,pprint
from pathlib import Path


def amp_cal_split(options:Options):
  '''
  split off amp and target(?) fields for calibration
  #split(vis =  msfile+".ms", outputvis = "init.ms", datacolumn = 'data', field = (source_id, ampcal_id), spw = used_spws)
  '''
  fields,spwID = get_command(options)

  if Path(options.initial_calibration_filename+".ms").is_dir():
    #raise Exception(f"{AMP_CAL_MS}.ms already exists, please move,delete, or rename it")
    ct.casalog.post(f"{options.proj_name+'.ms'} -> {options.initial_calibration_filename+'.ms'} | fields: {fields} | spw: {spwID}")
  else:
    ct.casalog.post(f"{options.proj_name+'.ms'} -> {options.initial_calibration_filename+'.ms'} | fields: {fields} | spw: {spwID}")
    ct.split(vis=options.proj_name+'.ms',outputvis=options.initial_calibration_filename+'.ms',datacolumn = 'data', field=fields, spw=spwID)
  #if options.get_dict_sp('breakpoints')['verify_scans']:
    #pause, show listobs(vis='init.ms') and continue if correct, else END


  if "manual_flagging" in options.breakpoints:
    print("Manual Data Flagging! ### NOT YET IMPLEMENTED")
    #open_plotms_thread(AMP_CAL_MS+".ms")
    print("Resuming Calibration Process...")


def get_command(options:Options):
  fields = define_split_fields(options)
  spwID = build_spwID(options)
  return fields,spwID
 
def build_spwID(options:Options):
  """build the spwID for splitting
  TODO: ADD BREAKPOINT CUSTOM SPW?
  """
  spwIDs = ''
  for spw in options.observation_data.spectral_windows:
    spwIDs = spwIDs + str(spw.id)
    spwIDs += ','
  return spwIDs[:-1] #remove last comma
  

def define_split_fields(options:Options):
  #needs multiple MS integration
  if options.self_phase_cal:
    print(f"Self Phase Calibration Selected, splitting | {str(options.source_ids.field_id)},{str(options.amp_cal.field_id)}")
    return str(options.source_ids.field_id) + ',' + str(options.amp_cal.field_id)
  else:
    print(f"splitting on fields('src,amp,phase) | {str(options.source_ids.field_id)},{str(options.amp_cal.field_id)},{str(options.phase_cal.field_id)} ")
    split_fields = str(options.source_ids.field_id) + ',' + str(options.amp_cal.field_id) + ',' + str(options.phase_cal.field_id)
  return split_fields

def open_plotms_thread(visfile):
  """
  call Plotms, find a way to cause a break :/
  """

  
