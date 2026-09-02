import casatasks as ct
from . import parse_listobs as parse

from classes.source_class import source_info
#from ..data_class import data
from classes.constants import *
from pre_calibration.options_class import Options

import sys,pprint
from pathlib import Path


def calibrator_split(options:Options):
  '''
  split off amp and target(?) fields for calibration
  #split(vis =  msfile+".ms", outputvis = "init.ms", datacolumn = 'data', field = (source_id, ampcal_id), spw = used_spws)
  '''
  fields,spwID = get_command(options)

  if Path(options.initial_calibration_filename+".ms").is_dir():
    #raise Exception(f"{PRIMARY_CAL_MS}.ms already exists, please move,delete, or rename it")
    ct.casalog.post(f"{options.proj_name+'.ms'} -> {options.initial_calibration_filename+'.ms'} | fields: {fields} | spw: {spwID}")
  else:
    ct.casalog.post(f"{options.proj_name+'.ms'} -> {options.initial_calibration_filename+'.ms'} | fields: {fields} | spw: {spwID}")
    ct.split(vis= MS_SUB_PATH + options.proj_name+'.ms',outputvis=options.initial_calibration_filename+'.ms',datacolumn = 'data', field=fields, spw=spwID)
  #if options.get_dict_sp('breakpoints')['verify_scans']:
    #pause, show listobs(vis='init.ms') and continue if correct, else END
  #NOTE: manual_flagging is deliberately NOT run here -- this executes inside a
  #LoadingAnimation worker thread and flagging is interactive. It runs from
  #hvla_data_cal.pre_data_calibration on the main thread, after this split.


def get_command(options:Options):

  fields = define_split_fields_phase_cal(options)
  spwID = build_spwID(options)
  return fields,spwID
 
def build_spwID(options:Options):
  """spw selection for the split: the science target's own spws (resolved in
  source_info.determine_band from the target's scans), so a multi-band archive MS is
  reduced to the band/spws the target was actually observed in.
  TODO: ADD BREAKPOINT CUSTOM SPW?
  """
  if options.spw_selection:
    return options.spw_selection
  #fallback (single-band MS, or selection not resolved): keep every spw
  return ','.join(str(spw.id) for spw in options.observation_data.spectral_windows)
  

def define_split_fields_phase_cal(options:Options):
  #needs multiple MS integration
  #(label, field_id) for each field that must be in the split. A target acting as
  #its own phase calibrator needs no separate one in the split.
  required = [('target', options.source_ids.field_id),
              ('flux calibrator', options.flux_cal.field_id)]
  if not options.target_is_phase_cal:
    required.append(('phase calibrator', options.phase_cal.field_id))

  #fail loudly if an id is missing rather than emitting malformed CASA syntax like "59,".
  #note: field id 0 is valid, so test for an empty string, not falsiness.
  missing = [label for label, fid in required if str(fid).strip() == '']
  if missing:
    raise ValueError(
      f"Cannot build split field selection: missing field id for {', '.join(missing)} "
      f"(calibrator detection likely failed upstream)."
    )

  split_fields = ','.join(str(fid) for _, fid in required)
  mode = 'target as its own phase cal (src,flux)' if options.target_is_phase_cal else 'src,flux,phase'
  print(f"Splitting on fields [{mode}]: {split_fields}")
  return split_fields


