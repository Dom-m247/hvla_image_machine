import casatasks as ct
import sys,os

from data_calibration import *
from classes.source_class import source_info
from classes.terminal_helper import LoadingAnimation
import pprint as pp
from .constants import *
from classes import *
from .options_class import Options
from pathlib import Path


def build_setjy(options):
  #pp.pp(options.get_dict())
  visfile = AMP_CAL_MS+'.ms'
  amp_field = '1'
  obs = options.split_observations
  #extract field ID for amp cal from listobs output
  for section in obs:
    if (section)[0:5] == 'field':
      if obs[section]['name'] == options.amp_cal.name:
        amp_field = str(section[len(section)-1:])
  
  use_model = options.amp_cal.model #+ ".im" #add +".im" to original add!
  ct.setjy(vis=visfile,field=amp_field,standard='Perley-Butler 2013',model=use_model,usescratch= True ,scalebychan=True,spw='')


def convert_to_ms(archive,options):
  """
  Converts raw HVLA data archive to Measurement Set (MS) format
  """
  #OUTPUT MS name = "fullMS.ms" -> weird cstring error if not directly entered.
  if (archive.endswith('.ms')):
    print(f"Archive {archive} is already in MS format.")
    archive = archive[:len(archive)-3]
    return parse.log_listobs(archive,options)
  #import archive to MS
  try:
    if not os.path.exists(FULLMS+'.ms'):
      LoadingAnimation.performing_action("archive import, This may take a moment",target=do_vla_import,args=(archive,FULLMS))
    return parse.log_listobs(FULLMS,options)
  except RuntimeError as file_exists:
    print(f"MS file already exists, delete it and re-run")
    sys.exit() # add call to a cleanup script?

def pre_data_calibration(options:Options):
  """extract and clean necessary info for data calibration"""
  list_obs = convert_to_ms(options.archive_file,options) 
  #extract info from listobs -> more complete than returned data
  options.observation_data = parse.populate_Obs_data(list_obs) 

  #find calibrators TODO: add phase calibration option
  options.amp_cal  = source_info(options,"amp_calibrator")
  LoadingAnimation.performing_action(" ms split on source and amp calibrator", target=cal_split.amp_cal_split, args=(options,))
  #print("running Amp Calibration...")
  #cal_split.amp_cal_split(options)
  split_list_obs = parse.log_listobs(AMP_CAL_MS,options)
  options.init_data = parse.populate_Obs_data(split_list_obs) 
  #set split off .ms field ID's for bandpass/gain cal
  options.source_ids.initial_ms_fieldID = options.source_ids.find_fieldID(options.init_data)
  options.amp_cal.initial_ms_fieldID = options.amp_cal.find_fieldID(options.init_data)

def data_calibration(options:Options):
  """
  main in for data calibration of HVLA data archive
  Creates MS files from raw data, applies calibration
  """
  pre_data_calibration(options)
  build_setjy(options)
  print("Performing Data Calibration...")
  main_calibrations.gain_cal(options)
  #split of calibrated data for imaging
  LoadingAnimation.performing_action(" calibrated data split", target=calibrated_split, args=(options,))

def calibrated_split(options:Options):
  """
  split off calibrated data for imaging
  """
  if not Path(CALIBRATED_MS).is_dir():
    ct.casalog.post(f"{AMP_CAL_MS+'.ms'} -> {CALIBRATED_MS}")
    ct.split(vis=AMP_CAL_MS+'.ms',outputvis=CALIBRATED_MS+'.ms',datacolumn = 'corrected', field=options.source_ids.fieldID)
    print(f"The calibrated data exists, not splitting")
    ct.casalog.post(f"{AMP_CAL_MS+'.ms'} -> {CALIBRATED_MS}")
  else:
    print(f"The calibrated data exists, not splitting")
    ct.casalog.post(f"{AMP_CAL_MS+'.ms'} -> {CALIBRATED_MS}")
  parse.log_listobs(CALIBRATED_MS,options)


def do_vla_import(archive_file:str,output_ms:str):
  """
  Convert VLA archive to Measurement Set format
  """
  print(f"Importing {archive_file} to {output_ms+'.ms'}...")
  ct.importvla(archivefiles={archive_file},vis=output_ms+'.ms')
  
  
