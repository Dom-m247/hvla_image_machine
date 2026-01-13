FULLMS = 'fullSet' #+".ms"
import casatasks as ct # type: ignore
import sys,os
#from .options_class import Options
#from .data_calibration import parse_list_obs as parse
from data_calibration import *
from classes.source_class import source_info
import pprint as pp
from .constants import *
from classes import *
from .options_class import Options

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
  print(f"Converting archive {archive} to Measurement Set format...")
  try:
    if not os.path.exists(FULLMS+'.ms'):
      print("This may take a moment...",end="")
      ct.importvla(archivefiles={archive},vis=FULLMS+'.ms')
      print("Done")
    return parse.log_listobs(FULLMS,options)
  except RuntimeError as file_exists:
    print(f"MS file already exists, delete it and re-run")
    sys.exit() # add call to a cleanup script?

def pre_data_calibration(options:Options):
  """extract and clean necessary info for data calibration"""
  list_obs = convert_to_ms(options.archive_file,options) 
  
  #extract info from listobs -> more complete than returned data
  parse.populate_Obs_data(list_obs,options) 

  #find calibrators TODO: add phase calibration option
  options.amp_cal  = source_info(options,"amp_calibrator")
  print("running Amp Calibration...")
  cal_split.amp_cal_split(options)

def data_calibration(options:Options):
  """
  main in for data calibration of HVLA data archive
  Creates MS files from raw data, applies calibration
  """
  pre_data_calibration(options)
  build_setjy(options)
  
  
