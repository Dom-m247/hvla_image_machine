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

def data_calibration(options:Options):
  """
  main in for data calibration of HVLA data archive
  Creates MS files from raw data, applies calibration
  """
  pre_data_calibration(options)
  build_setjy(options)
  print("Performing Data Calibration...")
  if not Path(options.calibrated_filename+'.ms').is_dir():
    main_calibrations.amp_phase_cal(options)
    #split of calibrated data for imaging
    LoadingAnimation.performing_action(" calibrated data split", target=calibrated_split, args=(options,))

def convert_to_ms(archive,options):
  """
  Converts raw HVLA data archive to Measurement Set (MS) format
  """
  #get some version of the observation Name
  #OUTPUT MS name = "fullMS.ms" -> weird cstring error if not directly entered.
  if (archive.endswith('.ms')):
    archive = archive[:len(archive)-3] #remove '.ms'
    options.proj_name = archive[archive.rfind('/')+1:]
    return parse.log_listobs(archive,options)
  #import archive to MS
  try:
    options.proj_name = archive[archive.rfind('/')+1:archive.rfind('/')+6] + '_' + FULLMS #attempt to extart the observtion proj code -> mostly for file naming    if not os.path.exists(options.proj_name + '.ms'):
    LoadingAnimation.performing_action("archive import, This may take a moment",target=do_vla_import,args=(archive,options.proj_name))
    return parse.log_listobs(options.proj_name,options)
  except RuntimeError as file_exists:
    print(f"MS file already exists, delete it and re-run")
    sys.exit() # add call to a cleanup script?

def do_vla_import(archive_file:str,output_ms:str):
  """
  Convert VLA archive to Measurement Set format
  """
  if not Path(output_ms+'.ms').is_dir():
    print(f"Importing {archive_file} to {output_ms+'.ms'}...")
    ct.importvla(archivefiles={archive_file},vis=output_ms+'.ms')

def pre_data_calibration(options:Options):
  """extract and clean necessary info for data calibration"""
  list_obs = convert_to_ms(options.archive_file,options) 

  #extract info from listobs -> more complete than returned data
  options.observation_data = parse.populate_Obs_data(list_obs) 

  #find calibrators TODO: add phase calibration option
  options.source_ids  = source_info(options,type="target",name=options.source)
  options.amp_cal  = source_info(options,type="flux_calibrator")
  options.phase_cal  = source_info(options,type="phase_cal")
  generate_file_names(options)
  #generate Naming Schemese for files
  LoadingAnimation.performing_action(" ms split on source, Flux/amp calibrator, and phase calibrator", target=cal_split.amp_cal_split, args=(options,))

  #split off the calibrators and target's to make cleaning and calibration more efficient
  split_list_obs = parse.log_listobs(options.initial_calibration_filename,options)
  options.init_data = parse.populate_Obs_data(split_list_obs) 
  #set split off .ms field ID's for bandpass/gain cal
  options.source_ids.initial_ms_fieldID = options.source_ids.find_fieldID(options.init_data)
  options.amp_cal.initial_ms_fieldID = options.amp_cal.find_fieldID(options.init_data)
  options.phase_cal.initial_ms_fieldID = options.phase_cal.find_fieldID(options.init_data)

def calibrated_split(options:Options):
  """
  split off calibrated data for imaging
  """
  if Path(options.calibrated_filename+'.ms').is_dir():
    print(f"The calibrated data exists, not splitting")
    ct.casalog.post(f"{options.initial_calibration_filename+'.ms'} -> {options.calibrated_filename+'.ms'}")
  else:
    ct.split(vis=options.initial_calibration_filename+'.ms',outputvis=options.calibrated_filename+'.ms',datacolumn = 'corrected', field=options.source_ids.name)
    ct.casalog.post(f"{options.initial_calibration_filename+'.ms'} -> {options.calibrated_filename+'.ms'}")
  parse.log_listobs(options.calibrated_filename,options)

def build_setjy(options):
  visfile = options.proj_name +'.ms'
  amp_field = '1'
  obs = options.split_observations 
  #extract field ID for amp cal from listobs output
  for section in obs:
    if (section)[0:5] == 'field':
      if obs[section]['name'] == options.amp_cal.name:
        amp_field = str(section[len(section)-1:])
  amp_field = options.amp_cal.name
  use_model = options.amp_cal.model 
  ct.setjy(vis=visfile,field=amp_field,standard='Perley-Butler 2013',model=use_model,usescratch= True,scalebychan=True,spw='')

def generate_file_names(options:Options):
  ''' set a variable that can be used to better generate filenames'''
  options.initial_calibration_filename = options.observation_data.obs_info.project + '_' +AMP_CAL_MS
  options.calibrated_filename = options.observation_data.obs_info.project + '_' +options.source_ids.name
  if options.image_filename is None:
    options.image_filename = options.source_ids.name +'_'+ options.band 