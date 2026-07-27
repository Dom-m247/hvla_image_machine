from casatasks import casalog
import sys
from typing import Any, cast
from classes.observations_class import Obs_data
from classes.source_class import source_info
from classes.constants import *
import pprint

class Options:
  """contains all the parameters, and options"""
  '''values for Dictionary keys:
  source, bands, breakpoints'''

  #Single source of truth for what round-trips through import.json. NED-derived
  #source_ra/source_decl/search_alias are intentionally excluded -- they're
  #re-derived from `source` on import (process_input_dict defaults them with .get()).
  #cell_size/self_cal_cycles are conditionally appended in generate_dict.
  IMPORT_FIELDS = (
    'source', 'archive_file', 'band', 'breakpoints', 'custom_amp_cal',
    'phase_calibrator_method', 'reference_antenna', 'min_snr', 'image_filename',
    'image_size', 'interactive_image', 'use_custom_cell_size', 'deconvolver',
    'weighting', 'do_self_cal', 'mask',
  )

  def __init__(self,sysArgs=None,
               source=None,
               archive_file = '',
               band='auto',
               breakpoints: list | None = None,
               custom_amp_cal='auto',
               reference_antenna='auto',
               min_snr=3.0,):
    #default members
    self.sysArgs: Any = sysArgs  #argparse.Namespace (dynamic dest attrs) -> Any
    self.source = source
    self.archive_file = archive_file
    self.band = band
    #normalize to a list so 'x in options.breakpoints' is always valid (never None)
    self.breakpoints = breakpoints if breakpoints is not None else []
    self.custom_amp_cal = False if custom_amp_cal == AUTO else True # temp var, not yet implemented
    self.reference_antenna = reference_antenna
    self.min_snr = min_snr
    self.source_ra = ''
    self.source_decl = ''
    self.search_alias = ''
    self.proj_code = ''            #project code of selected radio_search observation
    self.array_config = ''         #VLA config (A/B/C/D, incl. hybrids like BnA) of the selected observation; sizes the imaging cell in find_cell_size
    self.proj_name = ''            #proj_code + suffix, used for MS/file naming (set in convert_to_ms)
    self.archive_files = []        #list of raw archive files downloaded via radio_search
  
    #other members 
    #fileNames
    self.initial_calibration_filename = '' #ms/calbration tables include phase,amp and target
    self.calibrated_filename = '' #file name of calibrated source standalone MS

    self.observation_data = Obs_data() 
    #source_classe objects (deferred: populated by set_calibrators before use)
    self.source_ids = cast(source_info, None)
    self.amp_cal = cast(source_info, None)
    self.self_phase_cal = None #true/false
    self.phase_cal = cast(source_info, None)
    self.init_data = Obs_data()
    #extra members added during processing for tracking 
    self.ref_ant = cast(str, None)  #deferred: set by find_refant before gaincal/bandpass use
    self.split_observations = None
    self.spw_selection = '' #CSV of spw ids to keep for the split, derived from the target's own scans (set in source_info.resolve_run_band)
    self.solint = None
    #path to a saved clean mask (a tclean .mask image or a region file) to replay the
    #interactively-drawn regions; '' = none. Set from a saved run and round-trips
    #through import.json so --import can reproduce the mask non-interactively.
    self.mask = ''
    self.results_dir = '' #populated by Cleaner.collect_results; where replay.py is written
    self.best_image_base = '' #image_filename base of the best (lowest-RMS) self-cal cycle
    self.val = 0 #debugging variable
    # validate inputs below; else throw err 
       
  def process_input_dict(self,dict_in):
    """import options from dict's (from import.json/GUI/Terminal)"""
    if dict_in is None:
      print("Warning: input options is None, skipping update")
      return False
    try:
      self.source = dict_in['source']
      self.archive_file = dict_in['archive_file']
      self.band = dict_in['band']
      #NED-derived fields are not written to import.json; re-derived from `source`.
      self.source_ra = dict_in.get('source_ra', '')
      self.source_decl = dict_in.get('source_decl', '')
      self.search_alias = dict_in.get('search_alias', '')
      self.breakpoints = dict_in['breakpoints'] or []
      #self.custom_amp_cal = dict_in['custom_amp_cal']
      self.custom_amp_cal = False if dict_in['custom_amp_cal'] == AUTO else dict_in['custom_amp_cal'] # temp var, not yet implemented
      self.phase_calibrator_method = dict_in.get('phase_calibrator_method', AUTO)
      print(f"Calibration Method: {self.phase_calibrator_method}")
      self.reference_antenna = dict_in['reference_antenna']
      self.min_snr = dict_in['min_snr']
      self.image_filename = dict_in['image_filename']
      self.image_size = dict_in['image_size']
      self.interactive_image = dict_in['interactive_image']
      self.use_custom_cell_size = dict_in['use_custom_cell_size']
      if self.use_custom_cell_size:
        self.cell_size = dict_in['cell_size']
      self.deconvolver = dict_in['deconvolver']
      self.weighting = dict_in['weighting']
      self.do_self_cal = dict_in['do_self_cal']
      if self.do_self_cal:
        self.self_cal_cycles = dict_in['self_cal_cycles']
      #saved clean-mask path (older import.json files won't have it -> '')
      self.mask = dict_in.get('mask', '')
      casalog.post(f"Information added to obj: {dict_in}") #logging values added to data_set object
      return True
    except ValueError as e:
      print(f"an error occured processing an option: {e}")
      sys.exit()
    except KeyError as ke:
      print(f"Key Error processing options: {ke}")
      sys.exit()

  def to_dict(self):
    '''Snapshot of all members for export. Nested objects (source_info, Obs_data,
    argparse Namespace, numpy scalars, ...) are converted at json.dump time by
    import_settings._json_default, so this stays simple and None-safe -- no manual
    per-field .to_dict() calls that crash when a calibrator/data member is still unset.'''
    summary_dict = dict(self.__dict__)
    summary_dict.pop('split_observations', None) #bulky listobs result, omit from export
    return summary_dict
  
  def generate_dict(self):
    '''Build the dict written to import.json. Source of truth is IMPORT_FIELDS,
    plus two conditionally-present fields. process_input_dict reads these back.'''
    summary_dict = {k: getattr(self, k) for k in self.IMPORT_FIELDS}
    if self.use_custom_cell_size:
      summary_dict['cell_size'] = self.cell_size
    if self.do_self_cal:
      summary_dict['self_cal_cycles'] = self.self_cal_cycles
    return summary_dict


