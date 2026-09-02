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
  source, bands, decisions'''

  #Single source of truth for what round-trips through import.json. NED-derived
  #source_ra/source_decl/search_alias are intentionally excluded -- they're
  #re-derived from `source` on import (process_input_dict defaults them with .get()).
  #cell_size/self_cal_cycles are conditionally appended in generate_dict.
  IMPORT_FIELDS = (
    'source', 'archive_file', 'archive_files', 'band', 'decisions',
    'reference_antenna', 'flux_cal_name', 'flux_cal_manual', 'phase_cal_name',
    'min_snr', 'image_filename',
    'image_size', 'interactive_image', 'use_custom_cell_size', 'deconvolver',
    'weighting', 'robust', 'test_image', 'mask',
  )

  def __init__(self,sysArgs=None,
               source=None,
               archive_file = '',
               band='auto',
               decisions: dict | None = None,
               reference_antenna='auto',
               min_snr=3.0,):
    #default members
    self.sysArgs: Any = sysArgs  #argparse.Namespace (dynamic dest attrs) -> Any
    self.source = source
    self.archive_file = archive_file
    self.band = band
    #mode per decision point; always complete, so decision() never misses a key
    self.decisions = {k: v['default'] for k, v in DECISIONS.items()}
    if decisions:
      self.decisions.update(decisions)
    #answers recorded from an earlier run: these pre-empt prompting on --importRun
    self.flux_cal_name = ''        #chosen flux calibrator field name
    self.flux_cal_manual = None    #{'flux': Jy, 'reffreq': str} for setjy standard='manual'
    self.phase_cal_name = ''       #chosen phase calibrator field name
    self.reference_antenna = reference_antenna
    self.min_snr = min_snr
    self.source_ra = ''
    self.source_decl = ''
    self.search_alias = ''
    self.redshift = ''             #from NED; '' when NED has no measured redshift
    self.proj_code = ''            #project code of selected radio_search observation
    self.array_config = ''         #VLA config (A/B/C/D, incl. hybrids like BnA) of the selected observation; sizes the imaging cell in find_cell_size
    self.proj_name = ''            #proj_code + suffix, used for MS/file naming (set in convert_to_ms)
    self.archive_files = []        #every raw archive file of a multi-file segment
                                   #(radio_search download, or picked locally); importvla
                                   #concatenates them into one MS. Empty for a single archive/MS.
  
    #other members 
    #fileNames
    self.initial_calibration_filename = '' #ms/calbration tables include phase,amp and target
    self.calibrated_filename = '' #file name of calibrated source standalone MS

    self.observation_data = Obs_data() 
    #source_classe objects (deferred: populated by set_calibrators before use)
    self.source_ids = cast(source_info, None)
    self.flux_cal = cast(source_info, None)
    self.target_is_phase_cal = None #true/false
    self.phase_cal = cast(source_info, None)
    self.init_data = Obs_data()
    #extra members added during processing for tracking 
    self.ref_ant = cast(str, None)  #deferred: set by find_refant before gaincal/bandpass use
    self.split_observations = None
    self.spw_selection = '' #CSV of spw ids to keep for the split, derived from the target's own scans (set in source_info.resolve_run_band)
    self.solint = None
    self.self_cal_cycles = SELF_CAL_DEFAULT_CYCLES #overridden by the GUI/CLI when self-cal is on
    self.robust = CLEAN_ROBUST #briggs robust; run-level, so scored cycles stay comparable
    self.test_image = False #shallow throwaway clean to judge cell/imsize/robust first
    #path to a saved clean mask (a tclean .mask image or a region file) to replay the
    #interactively-drawn regions; '' = none. Set from a saved run and round-trips
    #through import.json so --import can reproduce the mask non-interactively.
    self.mask = ''
    self.results_dir = '' #populated by Cleaner.collect_results; where replay.py is written
    self.results_name = '' #<proj>_<source>_<band>; basename of every file in results_dir
    self.fit_record = {} #source_fit's measurements + Gaussian fit of the best image
    self.best_image_base = '' #image_filename base of the best (lowest-RMS) self-cal cycle
    self.coresub_base = '' #image base of the core-subtracted (jet) image, when it ran
    self.val = 0 #debugging variable
    # validate inputs below; else throw err 
       
  def process_input_dict(self,dict_in):
    """import options from dict's (from import.json/GUI/Terminal)"""
    if dict_in is None:
      print("Warning: input options is None, skipping update")
      return False
    try:
      self.source = dict_in['source']
      #a saved multi-file segment round-trips through archive_files; older
      #import.json files carry only the single archive_file path
      self.set_archive(dict_in.get('archive_files') or dict_in['archive_file'])
      self.band = dict_in['band']
      #NED-derived fields are not written to import.json; re-derived from `source`.
      self.source_ra = dict_in.get('source_ra', '')
      self.source_decl = dict_in.get('source_decl', '')
      self.search_alias = dict_in.get('search_alias', '')
      self.redshift = dict_in.get('redshift', '')
      #set when the observation came from an archive search; absent from older exports
      self.proj_code = dict_in.get('proj_code', '')
      if 'decisions' not in dict_in:
        raise ValueError(
          "this import.json predates Breakpoints 2.0: 'breakpoints' and "
          "'phase_calibrator_method' were replaced by a single 'decisions' map "
          f"({', '.join(DECISIONS)}). Re-run the GUI/CLI to produce a current file.")
      self.decisions.update(dict_in['decisions'] or {})
      print(f"Decisions: {self.decisions}")
      #recorded answers -- present only when an earlier run resolved them
      self.flux_cal_name = dict_in.get('flux_cal_name', '')
      self.flux_cal_manual = dict_in.get('flux_cal_manual')
      self.phase_cal_name = dict_in.get('phase_cal_name', '')
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
      self.robust = dict_in.get('robust', CLEAN_ROBUST)
      self.test_image = dict_in.get('test_image', False)
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

  @property
  def do_self_cal(self) -> bool:
    '''Derived from the self_cal decision, which is the single source of truth.'''
    return self.decision('self_cal') != OFF

  def decision(self, name) -> str:
    '''Mode chosen for decision `name`, falling back to the registry default so a
    newly-added decision never breaks an existing options object.'''
    return self.decisions.get(name, DECISIONS[name]['default'])

  def set_archive(self, paths):
    '''Record the archive selection. `paths` may be one path or a list of them.

    archive_file stays the single str every other consumer expects (the MS, or
    the first file of a segment); archive_files carries the whole segment for
    importvla, and is empty when there is only one file to import.
    '''
    if isinstance(paths, (list, tuple)):
      paths = [str(p) for p in paths]
      self.archive_files = paths if len(paths) > 1 else []
      self.archive_file = paths[0] if paths else ''
    else:
      self.archive_files = []
      #'' rather than None for an empty pick: every consumer does string work on it
      self.archive_file = str(paths) if paths else ''

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


