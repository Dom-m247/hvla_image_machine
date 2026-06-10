from pathlib import Path
from pprint import pp
import threading
import sys

from pre_calibration.options_class import Options
from classes.constants import *
from API_integrations.simbad import simbad
from API_integrations.NED import NED_API
class CLI:
  
  '''Helper functions for terminal interactions, managing input'''
  def getOptions(options:Options):
    '''
    get options from terminal input
    i.e breakpoints, min_snr, image info.
    '''

    print("For any Options, pressing enter will select an Auto option")
    CLI.getSourceInfo(options)
    options.archive_file = CLI.getObservationArchive()
    options.breakpoints = CLI.getBreakpoints()
    #options.custom_amp_cal = CLI.getCustomAmpCal()
    options.custom_amp_cal = False
    options.phase_calibrator_method = CLI.getPhaseCalibratorMethod()
    options.reference_antenna = CLI.getReferenceAntenna()
    options.min_snr = CLI.getMinSNR()
    options.image_filename = CLI.getImageFilename()
    options.image_size = CLI.getImageSize()
    options.interactive_image = CLI.getYesNo("Enable interactive imaging?")
    options.use_custom_cell_size = CLI.getYesNo("Use a custom cell size?")
    if options.use_custom_cell_size:
      options.cell_size = CLI.getCellSize()
    options.deconvolver = CLI.getDeconvolver()
    options.weighting = CLI.getWeighting()
    options.do_self_cal = CLI.getYesNo("Enable self-calibration?")
    if options.do_self_cal:
      options.self_cal_cycles = CLI.getSelfCalCycles()


  def getCalibrationOptions(options:Options):
    '''Gather calibration/imaging options for radio_search mode.
    Source info is collected during the radio search and the archive files are
    downloaded from the NAS, so both getSourceInfo and getObservationArchive
    are skipped here. Intended to run on its own thread alongside DelosDownload.
    '''
    print("For any Options, pressing enter will select an Auto option")
    options.breakpoints = CLI.getBreakpoints()
    options.custom_amp_cal = False
    options.phase_calibrator_method = CLI.getPhaseCalibratorMethod()
    options.reference_antenna = CLI.getReferenceAntenna()
    options.min_snr = CLI.getMinSNR()
    options.image_filename = CLI.getImageFilename()
    options.image_size = CLI.getImageSize()
    options.interactive_image = CLI.getYesNo("Enable interactive imaging?")
    options.use_custom_cell_size = CLI.getYesNo("Use a custom cell size?")
    if options.use_custom_cell_size:
      options.cell_size = CLI.getCellSize()
    options.deconvolver = CLI.getDeconvolver()
    options.weighting = CLI.getWeighting()
    options.do_self_cal = CLI.getYesNo("Enable self-calibration?")
    if options.do_self_cal:
      options.self_cal_cycles = CLI.getSelfCalCycles()

  def getSourceInfo(options:Options):
    '''
    get options from terminal input
    used for Radio Search and Terminal Calibration modes
    '''
    source_dict = CLI.get_source()
    options.source = source_dict['source']
    options.source_ra = source_dict['ra_decl']['ra']
    options.source_decl = source_dict['ra_decl']['decl']
    options.search_alias = source_dict['alias']
    options.band = CLI.getBand()

  def getBreakpoints():
    '''get the breakpoints to set for the script
      ie: data flagging, doing self-cal, manual clean, etc.
    '''
    while True:
      try:
        counter = 1
        for bp in BREAKPOINTS:
          print(f"{counter}: {BREAKPOINTS[bp]}")
          counter += 1
        selected = input("Enter the numbers of the breakpoints you want to set, separated by commas (e.g., 1,2,3): ")
        if selected == '':
          return []
        selected_indices = [int(x.strip()) for x in selected.split(',')]
        breakpoints = [list(BREAKPOINTS.keys())[i-1] for i in selected_indices if i-1 < len(BREAKPOINTS)]
        break 
      except ValueError:
        print("Invalid input. Please enter valid breakpoints.")
    return breakpoints

  def getBand():
    '''get band'''
    while True:
      try:
        band = input(f"Enter Band or press enter for none: ")
        if band == "":
          return 'auto'
        if (band not in BAND_GHZ_RANGES.keys()): #breaks for auto with Radio_search
          raise ValueError(f"Invalid band {band}. Please enter one of {list(BAND_GHZ_RANGES.keys())}.")
        break
      except ValueError:
        print("Invalid input. Please enter a valid band.")
    return band

  def getObservationArchive():
    '''get the data archive or MS'''
    while True:
      archive = input("Enter Path for Observation Archive or MS: ").strip()
      if not (archive.endswith('.ms') or archive.endswith('.exp')):
        print("Invalid input. Path must end in .ms or .exp.")
        continue
      if not Path(archive).is_dir() and not Path(archive).is_file():
        print(f"Path not found: {archive}")
        continue
      break
    return archive
  
  def get_source():
    '''get source name'''
    while True:
      try:
        source = input("Enter Source Name: ")
        if not (result := NED_API.obj_exists(source)):
          raise ValueError(f"Source {source} not found by NED. Please enter a valid source.")
        if(source == ''):
          sys.exit() #maybe auto/hold off till after import?
        break
      except ValueError:
        print("source not found. Please enter a valid name or press enter to canel.")
    result.update({'source':source})
    return result
  
  def getYesNo(prompt: str) -> bool:
    '''Generic yes/no prompt; defaults to No on empty input.'''
    while True:
      val = input(f"{prompt} [y/n]: ").strip().lower()
      if val == '':
        return False
      if val in ('y', 'yes'):
        return True
      if val in ('n', 'no'):
        return False
      print("Please enter y or n.")

  def getCustomAmpCal() -> str:
    '''Get amplitude calibrator; enter to use auto detection.'''
    val = input("Enter custom amplitude calibrator name (or press enter for auto): ").strip()
    return val if val else AUTO

  def getPhaseCalibratorMethod() -> str:
    '''Choose phase calibrator selection method.'''
    options_list = ["auto", "force phase calibrator", "pick phase calibrator"]
    while True:
      print("Phase calibrator method:")
      for i, opt in enumerate(options_list, 1):
        print(f"  {i}: {opt}")
      val = input("Select (or press enter for auto): ").strip()
      if val == '':
        return AUTO
      try:
        idx = int(val) - 1
        if 0 <= idx < len(options_list):
          return options_list[idx]
      except ValueError:
        if val in options_list:
          return val
      print(f"Invalid selection. Enter 1-{len(options_list)} or press enter.")

  def getReferenceAntenna() -> str:
    '''Get reference antenna; enter to use auto selection.'''
    val = input("Enter reference antenna name (or press enter for auto): ").strip()
    return val if val else AUTO

  def getMinSNR() -> float:
    '''Get minimum SNR for gaincal; enter for default 3.0.'''
    while True:
      val = input(f"Enter minimum SNR (or press enter for {MIN_SNR}): ").strip()
      if val == '':
        return MIN_SNR
      try:
        snr = float(val)
        if snr > 0:
          return snr
        print("SNR must be positive.")
      except ValueError:
        print("Invalid input. Please enter a number.")

  def getImageFilename() -> str:
    '''Get output image filename; enter to auto-generate.'''
    val = input("Enter image filename (or press enter to auto-generate): ").strip()
    return val if val else None

  def getImageSize() -> list:
    '''Get image size as a single side length (square); enter for default.'''
    default = DEFAULT_IMAGE_SIZE[0]
    while True:
      val = input(f"Enter image size in pixels (or press enter for {default}): ").strip()
      if val == '':
        return [default, default]
      try:
        size = int(val)
        if size > 0:
          return [size, size]
        print("Size must be a positive integer.")
      except ValueError:
        print("Invalid input. Please enter a whole number, e.g. 2048.")

  def getCellSize() -> str:
    '''Get cell size in arcseconds.'''
    while True:
      val = input("Enter cell size in arcseconds (e.g. 0.5arcsec or 0.5): ").strip()
      if val:
        if not val.endswith('arcsec'):
          val = val + 'arcsec'
        return val
      print("Cell size is required when custom cell size is enabled.")

  def getDeconvolver() -> str:
    '''Choose deconvolver algorithm.'''
    options_list = ["mtmfs", "hogbom", "clark", "multiscale", "mem", "clarkstokes", "asp"]
    while True:
      print("Deconvolver:")
      for i, opt in enumerate(options_list, 1):
        print(f"  {i}: {opt}")
      val = input(f"Select (or press enter for {options_list[0]}): ").strip()
      if val == '':
        return options_list[0]
      try:
        idx = int(val) - 1
        if 0 <= idx < len(options_list):
          return options_list[idx]
      except ValueError:
        if val in options_list:
          return val
      print(f"Invalid selection. Enter 1-{len(options_list)} or press enter.")

  def getWeighting() -> str:
    '''Choose imaging weighting scheme.'''
    options_list = ["briggs", "natural", "uniform", "superuniform", "radial", "briggsabs", "briggsbwtaper"]
    while True:
      print("Weighting:")
      for i, opt in enumerate(options_list, 1):
        print(f"  {i}: {opt}")
      val = input(f"Select (or press enter for {options_list[0]}): ").strip()
      if val == '':
        return options_list[0]
      try:
        idx = int(val) - 1
        if 0 <= idx < len(options_list):
          return options_list[idx]
      except ValueError:
        if val in options_list:
          return val
      print(f"Invalid selection. Enter 1-{len(options_list)} or press enter.")

  def getSelfCalCycles() -> int:
    '''Get number of self-calibration cycles.'''
    while True:
      val = input("Enter number of self-calibration cycles (default 3): ").strip()
      if val == '':
        return 3
      try:
        n = int(val)
        if n > 0:
          return n
        print("Must be a positive integer.")
      except ValueError:
        print("Invalid input. Please enter an integer.")

  def getOptionsFullCLI(options:Options):
    '''for organizing call order on full CLI no rs'''
    #get/unpack archive do listobs
    #get source 
    #get band
    #validate self-cal
    #else -> guess/choose calibrator
    pass

  def getRSArchive():
    '''a function to get the archive name from radio search'''
    while True:
      try:
        archive = input("Enter the archive Name: ")
        if(archive == ''):
          sys.exit()
        break
      except ValueError:
        print("something borked Please enter a valid name or press enter to canel.")
    return archive
  
  def fullCLI(options:Options):
    """Handles the procession for input via cli ->
    will ask user if not self-cal 
    """
    pass

  def selectObservation(observations) -> object:
    '''Display a table of nrao_observeration objects and prompt the user to select one.'''
    if not observations:
      print("No observations found.")
      return None

    header = (
      f"{'#':>3}  {'Date':<12} {'ProjCode':<12} {'Seg':<10} "
      f"{'Band':<5} {'Cfg':<5} {'Sensitivity':<12} {'Separation':<12} {'Time':<8} Name"
    )
    print(header)
    print('-' * (len(header) + 8))
    for i, obs in enumerate(observations, 1):
      print(
        f"{i:>3}  {obs.date:<12} {obs.proj_code:<12} {obs.seg:<10} "
        f"{obs.band:<5} {obs.cfg:<5} {obs.sensitivity:<12} {obs.separation:<12} {obs.time:<8} {obs.name}"
      )

    while True:
      val = input(f"\nSelect an observation by number (1-{len(observations)}, or press enter to cancel): ").strip()
      if val == '':
        return None
      try:
        idx = int(val)
        if 1 <= idx <= len(observations):
          return observations[idx - 1]
        print(f"Please enter a number between 1 and {len(observations)}.")
      except ValueError:
        print("Invalid input. Please enter a number.")

  def getManualPhaseCalibrator(options:Options):
    '''get manual phase calibrator name from user by listobs'''
    #print listobs
    print(f"List of potential phase calibrators from listobs: ")
    #fields_list = options.observation_data.fields
    for field in (fields_list:=options.observation_data.fields):
      print(f"  {field['name']}")