import casatasks as ct

#from pre_calibration.options_class import Options 
from classes.observations_class import Obs_data 
from classes.constants import *
from API_integrations.simbad import simbad
from API_integrations.NED import NED_API
import pprint
TYPE_FLUX_CAL = 'flux_calibrator'
TYPE_PHASE_CAL = 'phase_cal'
TYPE_TARGET = 'target'
AUTO = 'auto'

class source_info:
  #TODO: upgrade to utilize other 'better' claibrators
  def __init__(self,options,type='',name: str | None='',listobs_name='',source_id='',field_id=''):
    self.type = type
    self.name = name
    self.listobs_name = listobs_name
    self.source_id = source_id
    self.field_id = field_id
    self.ra = ''
    self.decl = ''
    #a premtive determination if band is set to auto
    if options.band == AUTO:
      self.find_bands(options)

    if self.type == TYPE_FLUX_CAL and not options.custom_amp_cal:
      print(f"finding flux cal!!!!!!!!!!!!!")
      if not self.detect_flux_cal_first(options):
        raise Exception('No Calibrator was detected for setJy')
    elif self.type == TYPE_PHASE_CAL and 'pick_calibrator' in options.breakpoints:
      pass
    elif self.type == TYPE_PHASE_CAL or (self.type == TYPE_TARGET and self.name is None): #would specifying a phase cal impede this logic?
      #search through fullset observation data and find 2nd most observed field?
      #also does source picking off most observed
      #self.detect_by_nrows(options,self.type) outdated, does not fuction consitiently

      self.find_phase_cal_distance(options)
    elif self.type == TYPE_FLUX_CAL and options.custom_amp_cal: #Change to Phase Cal? AND or Add phase cla
      self.manual_amp_cal(options)
    elif self.type == TYPE_TARGET and (self.name is not None):
      #a source was specified
      self.name = options.source
      #self.source_name = self.name
      self.source_id = self.find_source_id(options) #find source ID from source name may not work if given source name is doesn't match name in field.
      self.field_id = self.find_fieldID(options.observation_data)
      self.set_RA_DECL(options)
      
      #check_self_phase_cal = 
    #extra members defined by initial ms split after initilization
    self.initial_ms_fieldID: int | str | None = ''
  
  def find_fieldID(self,data_source):
    for field in data_source.fields:
      if field.name == self.listobs_name: 
        return field.id
      
  def _normalize_name(self, name):
    '''Strip B1950/J2000 epoch prefix (b/B/j/J) from a source name'''
    import re
    return re.sub(r'^[BbJj](?=\d)', '', name).strip()

  def find_source_id(self, options):
    '''find source_id from source name'''
    id = self.check_name_in_list_obs(options)
    if(id is not False):
      return id
    possible_names = simbad.formatted_names_list(options.search_alias)
    if possible_names is False:
      raise Exception(f"Source name {self.name} not found in listobs and not resolvable by SIMBAD")
    #strip the B1950/J2000 epoch prefix from BOTH sides before comparing: listobs
    #names carry it (e.g. 'B0206+35') while SIMBAD aliases often don't ('0206+35').
    normalized_aliases = {self._normalize_name(name) for name in possible_names}
    for sources in options.observation_data.sources:
      if self._normalize_name(sources.name) in normalized_aliases:
        self.listobs_name = sources.name
        return sources.id
    raise Exception(f"Source name {self.name} not found in listobs or SIMBAD with aliases {possible_names}")
     
  def check_name_in_list_obs(self, options):
    normalized = self._normalize_name(self.name)
    for sources in options.observation_data.sources:
      if sources.name == self.name or self._normalize_name(sources.name) == normalized:
        self.listobs_name = sources.name
        return sources.id
    return False
  
  def detect_by_nrows(self, options, source_type): #may be able to find 'source?'
    fields = options.observation_data.fields
    #pull n_terms
    fields_list = []
    source_field_entry = None
    for i in range(len(fields)):
      curr_field_id = fields[i].id
      curr_field_nrows = fields[i].nrows
      fields_list.append((curr_field_id,curr_field_nrows)) #maybe sketchy, curr_field_id ~= order in op.obs_data.fields or later
    #sort
    sorted_nrows = sorted(fields_list,key = lambda x: x[1],reverse=True) #sort by nrows in tuple
    if source_type == TYPE_TARGET:
      source_position = 0 #the location of the object to be used as a phase calibrator
      source_field_entry = fields[(sorted_nrows[source_position])[0]]
      pass
    if source_type == TYPE_PHASE_CAL:
      phase_cal_position = 1 #the location of the object to be used as a phase calibrator
      source_field_entry = fields[(sorted_nrows[phase_cal_position])[0]] # gets the field ID of the 2nd most observed field
    if source_field_entry is None:
      raise Exception(f"detect_by_nrows: unsupported source_type '{source_type}'")
    self.name = source_field_entry.name
    self.source_id = source_field_entry.src_id
    self.field_id = source_field_entry.id

  def set_RA_DECL(self,options):
    '''set RA and DECL coords for source'''
    for field in options.observation_data.fields:
      if field.id == self.field_id:
        self.ra = field.ra
        self.decl = field.decl

  def find_bands(self,options):
    '''
    Detects the bands for the source based on the spectral windows in the observation data.
    '''
    detected_bands = []
    if options.band == AUTO:
      for each_spw in options.observation_data.spectral_windows:
        for test_band,value in BAND_MHZ_RANGES.items():
          if self.in_spw(each_spw.ch0_mhz,value):
            if test_band not in detected_bands:
              detected_bands.append(test_band)
    else: 
      return options.band
    return detected_bands
  
  def asses_spw(self,options):
    '''checks if the SPW matches the input *and* define for model if auto'''
    band_option = options.band
    detected_bands = self.find_bands(options)

    if len(detected_bands) > 1:
      raise Exception('More than one band detected, Not yet implemented.')
    if band_option == 'auto':
      options.band = detected_bands[0] 
      return detected_bands[0]
    if band_option != detected_bands[0]:
      ct.casalog.post(f"The selected band: \'{band_option}\' doesn't match detected bands: {detected_bands}")
    return options.band

  def in_spw(self,listobs_spw,test_band):
    '''checks if a spw is within a range'''
                #lower range      upper range
    return True if (listobs_spw >= test_band[0]) and (listobs_spw <= test_band[1]) else False
    
  def detect_flux_cal_first(self,options):
    '''
    Finds the (first) Flux density calibrator in the full ms
    **** NEEDS TO BE UPDATED TO FIND CLOSEST FLUX 
    '''
    fields = options.observation_data.fields
    for i in range(len(fields)):
      for amp_cal in COMMON_AMPCALS_DICT:
        if fields[i].name == amp_cal or fields[i].name == COMMON_AMPCALS_DICT[amp_cal] :
          ct.casalog.post(f'Amp Cal found, ID:{amp_cal}, {COMMON_AMPCALS_DICT[amp_cal]}')
          self.name3c = COMMON_AMPCALS_DICT[amp_cal]
          self.name = fields[i].name
          self.listobs_name = fields[i].name
          self.field_id = fields[i].id 
          self.source_id = fields[i].src_id
          band = self.asses_spw(options) 
          options.band = band
          self.band = band
          self.model = self.name3c + '_' + self.band  +'.im'
          return True
    return False
  
  def check_self_phase_cal(self,options):
    '''checks ned  if self phase cal is doable'''
    if options.band == 'auto':
      self.asses_spw(options)
    #call NED by name, and RA DEC, check >=50mjy with 20% of band
    if options.phase_calibrator_method == 'auto':
      options.self_phase_cal = NED_API.check_self_cal_potential(self.name,options.band)
    else: 
      options.self_phase_cal = False #set self-calable to false to force phase calibrator usage.
    pass
  def manual_amp_cal(self,options):
    pass
  #def check_source_manual(data,source_id):
  #  '''checks that the manually entered source_id is in the observation'''
  #  for source in data.get_dict()['sources']:
  #    if source['name'] == source_id:
  #      ct.casalog.post('Amp Cal found, ID:{source_id}')
  #      data.add_dict({'amp_cal_source':'{source_id}'})
  #      return True
  #    else:
  #      return None
  def find_phase_cal_distance(self, options):
    '''
    Builds a dict of {field_id: (Fields, SkyCoord)} for all fields except the
    amp_cal and source target, sorts them by angular separation from the target,
    then picks the closest one that appears in the NRAO calibrator list for the
    current band.  Falls back to the closest field if none match.
    '''
    from astropy.coordinates import SkyCoord
    from classes.nrao_calibrators import NRAOCalibrators
    from typing import cast

    def _sep_deg(a: SkyCoord, b: SkyCoord) -> float:
      #astropy is untyped: .deg is a scalar float at runtime, narrow it for the checker
      return cast(float, a.separation(b).deg)

    def _to_skycoord(ra_str, decl_str) -> SkyCoord:
      # decl from listobs uses dot separators: +35.47.50.538 -> +35:47:50.538
      sign = decl_str[0] if decl_str[0] in '+-' else '+'
      parts = decl_str.lstrip('+-').split('.', 2)
      decl_colon = f"{sign}{parts[0]}:{parts[1]}:{parts[2]}"
      return SkyCoord(ra_str, decl_colon, unit=('hourangle', 'deg'))

    exclude_ids = {options.amp_cal.field_id, options.source_ids.field_id}

    # {field_id: (Fields object, SkyCoord)}
    candidates = {}
    for field in options.observation_data.fields:
      if field.id in exclude_ids:
        continue
      candidates[field.id] = (field, _to_skycoord(field.ra, field.decl))

    source_coord = _to_skycoord(options.source_ids.ra, options.source_ids.decl)

    # sort closest -> furthest from target
    sorted_candidates = sorted(
      candidates.items(),
      key=lambda item: _sep_deg(source_coord, item[1][1])
    )

    nrao = NRAOCalibrators()
    for field_id, (field, coord) in sorted_candidates:
      cal_entry = nrao.find_by_name(field.name)
      if cal_entry is not None and cal_entry.get_band(options.band) is not None:
        self.name = field.name
        self.listobs_name = field.name
        self.field_id = field.id
        self.source_id = field.src_id
        self.set_RA_DECL(options)
        sep = _sep_deg(source_coord, coord)
        ct.casalog.post(f'Phase cal: {self.name} ({sep:.2f} deg from target)')
        if sep > 10:
          ct.casalog.post(f'WARNING: Phase calibrator {self.name} is {sep:.2f} deg from target — calibration may be degraded.', priority='WARN')
          print(f"WARNING: Phase calibrator '{self.name}' is {sep:.2f} degrees from target source. Calibration quality may be degraded.")
        return

    # fallback: closest field even if not confirmed in NRAO list
    if sorted_candidates:
      field_id, (field, coord) = sorted_candidates[0]
      self.name = field.name
      self.listobs_name = field.name
      self.field_id = field.id
      self.source_id = field.src_id
      self.set_RA_DECL(options)
      sep = _sep_deg(source_coord, coord)
      ct.casalog.post(f'Phase cal (NRAO unconfirmed): {self.name} ({sep:.2f} deg from target)')
      if sep > 10:
        ct.casalog.post(f'WARNING: Phase calibrator {self.name} is {sep:.2f} deg from target — calibration may be degraded.', priority='WARN')
        print(f"WARNING: Phase calibrator '{self.name}' is {sep:.2f} degrees from target source. Calibration quality may be degraded.")
  
  @staticmethod
  def verify_model(data):
    '''
      verify that the amp calibrator alligns with the selceted Band
      May become unecessary if archive is downloaded
    '''
    pass
 
  def to_dict(self):
    return self.__dict__
    