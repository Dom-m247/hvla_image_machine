import casatasks as ct
import sys,os

from classes import CLI_input
from data_calibration import *
from classes.source_class import source_info
from classes.Loading_Animation import LoadingAnimation
from classes.constants import *
from classes import *
from pre_calibration.options_class import Options #self referential problem/
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
    if not options.self_phase_cal:
      main_calibrations.amp_phase_cal(options)
    else: 
      main_calibrations.self_phase_cal(options)
    #split of calibrated data for imaging
    LoadingAnimation.performing_action(" calibrated data split", target=calibrated_split, args=(options,))
  
def convert_to_ms(archive,options):
  """
  Converts raw HVLA data archive to Measurement Set (MS) format.
  `archive` may be a single archive/MS path (GUI/CLI mode) or a list of raw
  archive files downloaded via radio_search (all imported into one MS).
  """
  #radio_search path: a list of raw VLA archive files for the selected segment
  if isinstance(archive, list):
    try:
      options.proj_name = options.proj_code + '_' + FULLMS #use selected observation's project code for naming
      LoadingAnimation.performing_action("archive import, This may take a moment",target=do_vla_import,args=(archive,options.proj_name))
      return parse.log_listobs(MS_SUB_PATH+options.proj_name,options)
    except RuntimeError as file_exists:
      print(f"MS file already exists, delete it and re-run")
      sys.exit() # add call to a cleanup script?
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
    return parse.log_listobs(MS_SUB_PATH+options.proj_name,options)
  except RuntimeError as file_exists:
    print(f"MS file already exists, delete it and re-run")
    sys.exit() # add call to a cleanup script?

def do_vla_import(archive_files,output_ms:str):
  """
  Convert VLA archive to Measurement Set format.
  `archive_files` may be a single archive file path or a list of raw archive
  files; importvla concatenates a list of files into one MS.
  """
  if isinstance(archive_files, str):
    archive_files = [archive_files]
  #NOTE: importvla needs local paths it can open. For the radio_search path,
  #      the entries must be the LOCAL paths the NAS files were downloaded to,
  #      not the bare archive file names. DelosDownload sets these local paths.
  if not Path(MS_SUB_PATH + output_ms+'.ms').is_dir():
    print(f"\nImporting {archive_files} to {MS_SUB_PATH + output_ms+'.ms'}...")
    ct.importvla(archivefiles=archive_files,vis= MS_SUB_PATH + output_ms+'.ms')

def pre_data_calibration(options:Options):
  """extract and clean necessary info for data calibration"""
  #radio_search downloads a list of raw archive files; otherwise use the single archive/MS path
  archive = options.archive_files if options.archive_files else options.archive_file
  list_obs = convert_to_ms(archive,options)

  #extract info from listobs -> more complete than returned data
  options.observation_data = parse.populate_Obs_data(list_obs)
  #confirm band if not set, attempt to determine from source redshift
  
  #find calibrators TODO: add phase calibration option
  set_calibrators(options)
  print_calibration_summary(options)
  generate_file_names(options)
  #generate Naming Schemese for files
  LoadingAnimation.performing_action(" ms split on science target and calibrator(s)", target=cal_split.amp_cal_split, args=(options,))

  #data-flagging breakpoint: interactive (plotms + accept/revert prompt), so it runs
  #here on the main thread AFTER the split animation finishes -- not inside
  #amp_cal_split, which executes on a LoadingAnimation worker thread.
  if "manual_flagging" in options.breakpoints:
    data_flagging.manual_flagging(options)

  #split off the calibrators and target's to make cleaning and calibration more efficient
  split_list_obs = parse.log_listobs_precalib(options.initial_calibration_filename,options)
  options.init_data = parse.populate_Obs_data(split_list_obs) 
  #set split off .ms field ID's for bandpass/gain cal and find new field ID
  options.source_ids.initial_ms_fieldID = options.source_ids.find_fieldID(options.init_data)
  options.amp_cal.initial_ms_fieldID = options.amp_cal.find_fieldID(options.init_data)
  print(f"flux cal field ID: {options.amp_cal.initial_ms_fieldID} | source field ID: {options.source_ids.initial_ms_fieldID}")
  if not options.self_phase_cal:
    options.phase_cal.initial_ms_fieldID = options.phase_cal.find_fieldID(options.init_data)

def calibrated_split(options:Options):
  """
  split off calibrated data for imaging
  """
  if Path(options.calibrated_filename+'.ms').is_dir():
    print(f"The calibrated data exists, not splitting")
    ct.casalog.post(f"{options.initial_calibration_filename+'.ms'} -> {options.calibrated_filename+'.ms'}")
  else:
    ct.split(vis=options.initial_calibration_filename+'.ms',outputvis=options.calibrated_filename+'.ms',datacolumn = 'corrected', field=options.source_ids.listobs_name)
    ct.casalog.post(f"{options.initial_calibration_filename+'.ms'} -> {options.calibrated_filename+'.ms'}")
  parse.log_listobs(options.calibrated_filename,options)

def build_setjy(options):
  visfile = MS_SUB_PATH + options.proj_name +'.ms'
  #setjy runs on the full pre-split MS, so select the amp cal by name: names are stable
  #across the calibrator split, unlike field IDs (which renumber). initial_ms_fieldID
  #retains the split-MS id for main_calibrations; it is not valid against this full MS.
  amp_field = options.amp_cal.listobs_name
  use_model = options.amp_cal.model
  ct.setjy(vis=visfile,field=amp_field,standard='Perley-Butler 2013',model=use_model,usescratch= True,scalebychan=True,spw='')

def generate_file_names(options:Options):
  ''' set a variable that can be used to better generate filenames'''

  options.initial_calibration_filename = MS_SUB_PATH + options.observation_data.obs_info.project + '_' +AMP_CAL_MS
  options.calibrated_filename = MS_SUB_PATH + options.observation_data.obs_info.project + '_' +options.source_ids.name
  if options.image_filename is None:
    options.image_filename = MS_SUB_PATH + options.observation_data.obs_info.project + "_" + options.source_ids.name +'_'+ options.band 


#def determine_self_calibrator(options:Options,):
#  '''attempt to determine calibrator or self-cal'''
#  options.source_ids  = source_info(options,type="target",name=options.source)

def print_calibration_summary(options:Options):
  '''Pretty-print the resolved science target and calibrators.
  The phase calibrator is only shown when the target is not self phase calibrated.'''
  width = 60

  def _source_block(title, src):
    print('-' * width)
    print(f" {title}")
    if src is None:
      print("   (none)")
      return
    rows = [
      ("Name",         getattr(src, 'name', '')),
      ("Listobs name", getattr(src, 'listobs_name', '')),
      ("Field ID",     getattr(src, 'field_id', '')),
      ("Source ID",    getattr(src, 'source_id', '')),
      ("RA / Dec",     f"{getattr(src, 'ra', '')} / {getattr(src, 'decl', '')}"),
    ]
    #amp/flux calibrator carries band + setjy model info
    if getattr(src, 'band', None):
      rows.append(("Band", src.band))
    if getattr(src, 'model', None):
      rows.append(("Model", src.model))
    for label, value in rows:
      print(f"   {label:<13}: {value}")

  print('=' * width)
  print(" Calibration Summary")
  _source_block("Science Target", options.source_ids)
  _source_block("Flux Calibrator", options.amp_cal)
  if options.self_phase_cal:
    print('-' * width)
    print(" Phase Calibrator")
    print("   Self phase calibrated")
  else:
    _source_block("Phase Calibrator", getattr(options, 'phase_cal', None))
  print('=' * width)

def set_calibrators(options:Options):
  '''set calibrator objects in options'''
  #check self_cal first
  if(options.sysArgs.cli or options.sysArgs.cliCalib):
    #fluxCal = CLI_input.getFluxCal(options)
    ##ampCal = CLI_input.getAmpCal(options) not yet implemented
    #phaseCal = CLI_input.getPhaseCal(options)
    pass
  #build the target first: it resolves the observing band (from its own spws,
  #or honors a user-set band), which the flux-cal assessment then relies on.
  options.source_ids = source_info(options,type="target",name=options.source)
  options.amp_cal = source_info(options,type="flux_calibrator")
  options.source_ids.check_self_phase_cal(options)
  if not options.self_phase_cal:
    if options.phase_calibrator_method == "pick phase calibrator":
      #phaseCal = CLI_input.getPhaseCal(options)
      #return
      pass
    options.phase_cal  = source_info(options,type="phase_cal")