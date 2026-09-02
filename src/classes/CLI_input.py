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
  @staticmethod
  def getOptions(options:Options):
    '''
    get options from terminal input
    i.e decisions, min_snr, image info.
    '''

    print("For any Options, pressing enter will select an Auto option")
    CLI.getSourceInfo(options)
    options.set_archive(CLI.getObservationArchive())
    options.decisions = CLI.getDecisions()
    #only worth asking when the user wants a say; 'auto' picks its own
    if options.decision('refant') != AUTO:
      options.reference_antenna = CLI.getReferenceAntenna()
    options.min_snr = CLI.getMinSNR()
    options.image_filename = CLI.getImageFilename()
    options.image_size = CLI.getImageSize()
    options.interactive_image = CLI.getYesNo("Enable interactive imaging?")
    options.use_custom_cell_size = CLI.getYesNo("Use a custom cell size?")
    if options.use_custom_cell_size:
      options.cell_size = CLI.getCellSize(options.band)
    options.deconvolver = CLI.getDeconvolver()
    options.weighting = CLI.getWeighting()
    options.test_image = CLI.getYesNo("Make a test image first (to check cell/image size)?")
    if options.do_self_cal:   #set by the self_cal decision above
      options.self_cal_cycles = CLI.getSelfCalCycles()


  @staticmethod
  def getCalibrationOptions(options:Options):
    '''Gather calibration/imaging options for radio_search mode.
    Source info is collected during the radio search and the archive files are
    downloaded from the NAS, so both getSourceInfo and getObservationArchive
    are skipped here. Intended to run on its own thread alongside DelosDownload.
    '''
    print("For any Options, pressing enter will select an Auto option")
    options.decisions = CLI.getDecisions()
    #only worth asking when the user wants a say; 'auto' picks its own
    if options.decision('refant') != AUTO:
      options.reference_antenna = CLI.getReferenceAntenna()
    options.min_snr = CLI.getMinSNR()
    options.image_filename = CLI.getImageFilename()
    options.image_size = CLI.getImageSize()
    options.interactive_image = CLI.getYesNo("Enable interactive imaging?")
    options.use_custom_cell_size = CLI.getYesNo("Use a custom cell size?")
    if options.use_custom_cell_size:
      options.cell_size = CLI.getCellSize(options.band)
    options.deconvolver = CLI.getDeconvolver()
    options.weighting = CLI.getWeighting()
    options.test_image = CLI.getYesNo("Make a test image first (to check cell/image size)?")
    if options.do_self_cal:   #set by the self_cal decision above
      options.self_cal_cycles = CLI.getSelfCalCycles()

  @staticmethod
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
    options.redshift = source_dict.get('redshift', '')
    options.band = CLI.getBand()

  @staticmethod
  def _select(label, options_list, default) -> str:
    '''Numbered choice from a list; enter takes `default`. The shape every
    list-valued prompt here uses.'''
    while True:
      print(f"{label}:")
      for i, opt in enumerate(options_list, 1):
        print(f"  {i}: {opt}")
      val = input(f"Select (or press enter for {default}): ").strip()
      if val == '':
        return default
      try:
        idx = int(val) - 1
        if 0 <= idx < len(options_list):
          return options_list[idx]
      except ValueError:
        if val in options_list:
          return val
      print(f"Invalid selection. Enter 1-{len(options_list)} or press enter.")

  @staticmethod
  def getDecisions():
    '''Pick a mode for each decision point (see DECISIONS).'''
    return {name: CLI._select(spec['label'], list(spec['modes']), spec['default'])
            for name, spec in DECISIONS.items()}

  @staticmethod
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

  @staticmethod
  def getObservationArchive():
    '''Get the observation archive(s) or MS, as a list of paths.

    A VLA segment is often held locally as several raw archive files that
    importvla concatenates into one MS, so more than one may be given: separate
    the paths with commas, or name the folder holding them. A single archive or
    MS comes back as a one-entry list.
    '''
    while True:
      raw = input("Enter Path for Observation Archive or MS "
                  "(comma-separated for a multi-file segment, or a folder of archive files): ").strip()
      if not raw:
        print("Please enter a path.")
        continue
      if paths := CLI._resolve_archive_paths(raw):
        return paths

  @staticmethod
  def _resolve_archive_paths(raw):
    '''One archive selection -> list of paths, or [] with the reason printed.

    A lone folder that is not itself an MS is expanded to the archive files
    inside it, which is how a downloaded segment sits on disk
    (data_archive/<proj_code>/).
    '''
    entries = [Path(part.strip()).expanduser() for part in raw.split(',') if part.strip()]
    if not entries:
      return []
    if len(entries) == 1 and entries[0].is_dir() and entries[0].suffix != '.ms':
      found = sorted(p for p in entries[0].iterdir() if p.suffix in ARCHIVE_SUFFIXES)
      if not found:
        print(f"No archive files ({', '.join(ARCHIVE_SUFFIXES)}) in {entries[0]}")
        return []
      print(f"Found {len(found)} archive file(s) in {entries[0]}:")
      for path in found:
        print(f"  {path.name}")
      return [str(p) for p in found]
    paths = []
    for entry in entries:
      if not (entry.is_dir() or entry.is_file()):
        print(f"Path not found: {entry}")
        return []
      if entry.is_dir() and entry.suffix != '.ms':
        #only expanded when it is the whole selection, so it cannot be mixed with files
        print(f"Give the folder {entry.name} on its own to import the segment inside it.")
        return []
      if entry.suffix == '.ms':
        #an MS is already imported data; it cannot be concatenated with raw archives
        if len(entries) > 1:
          print("An MS must be given on its own, not alongside other files.")
          return []
      elif entry.suffix not in ARCHIVE_SUFFIXES:
        print(f"Invalid input. {entry.name} must end in .ms or {' / '.join(ARCHIVE_SUFFIXES)}.")
        return []
      paths.append(str(entry))
    return paths
  
  @staticmethod
  def get_source():
    '''get source name'''
    while True:
      try:
        source = input("Enter Source Name (or press enter to quit): ").strip()
        #test for the cancel BEFORE the lookup: NED does not resolve '', so an
        #empty name would otherwise come back "not found" and re-prompt forever
        if(source == ''):
          sys.exit() #maybe auto/hold off till after import?
        if not (result := NED_API.obj_exists(source)):
          raise ValueError(f"Source {source} not found by NED. Please enter a valid source.")
        break
      except ValueError:
        print("source not found. Please enter a valid name or press enter to cancel.")
    result.update({'source':source})
    return result
  
  @staticmethod
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

  @staticmethod
  def selectBand(bands, requested=None) -> str:
    '''Prompt the user to choose one band from the bands the target was actually
    observed in. Used when a requested band is not among them.'''
    while True:
      if requested:
        print(f"Requested band '{requested}' is not available for this target.")
      print("Bands observed for the target:")
      for i, b in enumerate(bands, 1):
        print(f"  {i}: {b}")
      val = input(f"Select a band (1-{len(bands)}): ").strip()
      try:
        idx = int(val) - 1
        if 0 <= idx < len(bands):
          return bands[idx]
      except ValueError:
        if val in bands:
          return val
      print(f"Invalid selection. Enter 1-{len(bands)} or a band name.")

  @staticmethod
  def getReferenceAntenna() -> str:
    '''Name a reference antenna outright. Only asked in 'manual' mode; enter defers
    to the run-time picker, which lists the ranked antennas once the MS is read.'''
    val = input("Enter reference antenna name (or press enter to pick one at run time): ").strip()
    return val if val else AUTO

  @staticmethod
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

  @staticmethod
  def getImageFilename() -> str | None:
    '''Get output image filename; enter (returns None) to auto-generate.'''
    val = input("Enter image filename (or press enter to auto-generate): ").strip()
    return val if val else None

  @staticmethod
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

  @staticmethod
  def getCellSize(band=None) -> str:
    '''Get cell size in arcseconds. If a resolved band is given, the example in
    the prompt uses the recommended cell (~1/10 of the band's angular resolution
    for the current array config, matching Cleaner.find_cell_size). Any value is
    accepted. Band may be 'auto' (not yet resolved), which uses a generic example.'''
    example = '0.5'
    if band and band != 'auto' and band in BAND_ANGULAR_RESOLUTION:
      example = f"{BAND_ANGULAR_RESOLUTION[band][ARRAY_CONFIGURATION] / 10:g}"
    while True:
      val = input(f"Enter cell size in arcseconds (e.g. {example}arcsec or {example}): ").strip()
      if val:
        if not val.endswith('arcsec'):
          val = val + 'arcsec'
        return val
      print("Cell size is required when custom cell size is enabled.")

  @staticmethod
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

  @staticmethod
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

  @staticmethod
  def getSelfCalCycles() -> int:
    '''Get number of self-calibration cycles. Default 4 so the full phase-only
    solint ladder (SELF_CAL_SOLINTS: inf -> 60s -> 30s -> int) can run before the
    a&p pass; fewer cycles just use the leading entries.'''
    while True:
      val = input("Enter number of self-calibration cycles (default 4): ").strip()
      if val == '':
        return 4
      try:
        n = int(val)
        if n > 0:
          return n
        print("Must be a positive integer.")
      except ValueError:
        print("Invalid input. Please enter an integer.")

  @staticmethod
  def getOptionsFullCLI(options:Options):
    '''for organizing call order on full CLI no rs'''
    #get/unpack archive do listobs
    #get source 
    #get band
    #validate self-cal
    #else -> guess/choose calibrator
    pass

  @staticmethod
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
  
  @staticmethod
  def fullCLI(options:Options):
    """Handles the procession for input via cli ->
    will ask user if not self-cal 
    """
    pass

  #Observations from this year onward are highlighted red in the selection table
  #(radio_search2 dates are 'YY-Mon-DD', so 09 == 2009).
  RADIO_SEARCH_HIGHLIGHT_YEAR = 2009
  _RED = '\033[31m'
  _RESET = '\033[0m'

  @staticmethod
  def _observation_year(date_str):
    '''Parse the 4-digit year from a radio_search2 date. Dates come as 'YY-Mon-DD'
    (e.g. '03-Dec-01'); a 4-digit 'YYYY-...' form is also accepted. 2-digit years
    pivot at 69 (69-99 -> 19xx, else 20xx). Returns an int year, or None.'''
    token = (date_str or '').split('-')[0].strip()
    if not token.isdigit():
      return None
    if len(token) == 4:
      return int(token)
    if len(token) == 2:
      n = int(token)
      return 1900 + n if n >= 69 else 2000 + n
    return None

  @staticmethod
  def selectObservation(observations) -> object:
    '''Display a table of nrao_observeration objects and prompt the user to select one.
    Rows observed in RADIO_SEARCH_HIGHLIGHT_YEAR or later are shown in red.'''
    if not observations:
      print("No observations found.")
      return None

    header = (
      f"{'#':>3}  {'Date':<12} {'ProjCode':<12} {'Seg':<10} "
      f"{'Band':<5} {'Cfg':<5} {'Sensitivity':<12} {'Separation':<12} {'Time':<8} Name"
    )
    print(header)
    print('-' * (len(header) + 8))
    print(f"{CLI._RED}Red{CLI._RESET} = observed {CLI.RADIO_SEARCH_HIGHLIGHT_YEAR} or later")
    for i, obs in enumerate(observations, 1):
      row = (
        f"{i:>3}  {obs.date:<12} {obs.proj_code:<12} {obs.seg:<10} "
        f"{obs.band:<5} {obs.cfg:<5} {obs.sensitivity:<12} {obs.separation:<12} {obs.time:<8} {obs.name}"
      )
      year = CLI._observation_year(obs.date)
      if year is not None and year >= CLI.RADIO_SEARCH_HIGHLIGHT_YEAR:
        row = f"{CLI._RED}{row}{CLI._RESET}"
      print(row)

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

