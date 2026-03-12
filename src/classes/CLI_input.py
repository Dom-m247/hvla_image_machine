from pathlib import Path
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
    options.breakpoints = CLI.getBreakpoints()

    pass

  def getSourceInfo(options:Options):
    '''
    get options from terminal input
    used for Radio Search and Terminal Calibration modes
    '''
    source_dict = CLI.get_source()
    options.source = source_dict['source']
    options.source_ra = source_dict['ra_decl'][0]
    options.source_decl = source_dict['ra_decl'][1]
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
        breakpoints = [list(BREAKPOINTS.keys())[i] for i in selected_indices if i <= len(BREAKPOINTS)]
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
          break
        if (band not in BAND_GHZ_RANGES.keys()): #breaks for auto with Radio_search
          raise ValueError(f"Invalid band {band}. Please enter one of {list(BAND_GHZ_RANGES.keys())}.")
        break
      except ValueError:
        print("Invalid input. Please enter a valid band.")
    return band

  def getObservationArchive():
    '''get the data archive or MS'''
    while True:
      try:
        archive = input("Enter Observation Archive or MS: ")
        if archive.endswith('.ms') or archive.endswith('.exp'):
          if not Path(archive).is_dir()or not Path(archive).is_file():
            raise ValueError(f"MS {archive} not found. Please enter a valid MS path.")
          break
      except ValueError:
        print("Invalid input. Please enter a valid path.")
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