from pathlib import Path
import threading

from pre_calibration.options_class import Options
from classes.constants import *
from simbad_integration import simbad
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
    options.source = CLI.get_source()
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

  def getBand(auto):
    '''get band'''
    while True:
      try:
        band = input(f"Enter Band{auto}: ")
        if band not in BAND_GHZ_RANGES.keys() or band == '': #breaks for auto with Radio_search
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
        if not simbad.validate_source(source):
          raise ValueError(f"Source {source} not found in Simbad. Please enter a valid source.")
        break
      except ValueError:
        print("Invalid input. Please enter a valid source name.")
    return source