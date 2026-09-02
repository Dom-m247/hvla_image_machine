from casatasks import casalog
import pprint
import re


#Antennas retrofitted during the EVLA transition appear as 'EA##' while the rest
#of the same array is still 'VA##'. The observation is pre-upgrade data either
#way, so anything shown to the user names every antenna the VLA way.
_EVLA_NAME = re.compile(r'[eE][aA](\d+)')


def vla_antenna_name(name):
  """An antenna name under VLA conventions ('EA01' -> 'VA01').

  DISPLAY ONLY. Antenna.name keeps the spelling the measurement set uses,
  because that is what CASA resolves antenna selections against and what
  flagdata reports back -- normalising it would break both.
  """
  text = str(name or '').strip()
  match = _EVLA_NAME.fullmatch(text)
  return f"VA{match.group(1)}" if match else text


class Obs_information:
    def __init__(self,obs_info={}):
      self.observer = obs_info['observer'] #will likeley be empty
      self.project = obs_info['project'] #IMPORTAN
      self.observtion = obs_info['observation'] #instrement 
      self.data_records = obs_info['data_records']

class Spectral_Windows:
    def __init__(self,spectral_windows=[]):
      self.id = spectral_windows['id']
      self.name = spectral_windows['name']
      self.num_channels = spectral_windows['num_channels']
      self.frame = spectral_windows['frame']
      self.ch0_mhz = spectral_windows['ch0_mhz']
      self.chanwid_khz = spectral_windows['chanwid_khz']
      self.totbw_khz = spectral_windows['totbw_khz']
      self.ctrfreq_mhz = spectral_windows['ctrfreq_mhz']
      self.correlations = spectral_windows['correlations']
    def to_dict(self):
      return self.__dict__

class Observations:
  def __init__(self, observations=[]):
    self.date = observations['date']
    self.timerange_start = observations['timerange_start']
    self.timerange_end = observations['timerange_end']
    self.scan = observations['scan']
    self.field_id = observations['field_id']
    self.field_name = observations['field_name']
    self.nrows = observations['nrows']
    self.spw_ids = observations['spw_ids']
    self.average_intervals = observations['average_intervals']
  def to_dict(self):
    return self.__dict__
  
class Sources:
  def __init__(self,sources={}):
    self.id = sources['id']
    self.name = sources['name']
    self.SpwId = sources['SpwId']
    self.RestFreq = sources['RestFreq']
    self.SysVel = sources['SysVel']
  def to_dict(self):
    return self.__dict__ 
  
class Fields:
  def __init__(self,field={}):
    self.id = field['id']
    self.code = field['code']
    self.name = field['name']
    #as listobs writes them: RA 'hh:mm:ss.ss', decl '+dd.mm.ss.ss' (dot-separated).
    #source_class._to_skycoord does the conversion where coordinates are needed.
    self.ra = field['ra']
    self.decl = field['decl']
    self.epoch = field['epoch']
    self.src_id = field['src_id']
    self.nrows = field['nrows']
  def to_dict(self):
    return self.__dict__

class Antenna:
  def __init__(self, antenna={}):
    self.id = antenna['id']
    self.name = antenna['name']
    self.station = antenna['station']
    self.diameter = antenna['diameter']
    self.longitude = antenna['longitude']
    self.latitude = antenna['latitude']
    self.east_offset = antenna['east_offset']
    self.north_offset = antenna['north_offset']
    self.elevation = antenna['elevation']
    self.x = antenna['x']
    self.y = antenna['y']
    self.z = antenna['z']

  @property
  def vla_name(self):
    """This antenna under VLA naming, for display. See vla_antenna_name."""
    return vla_antenna_name(self.name)

  def to_dict(self):
    #a property is not in __dict__, so exports keep the measurement set's own
    #spelling -- which is what makes them reproducible
    return self.__dict__

class Obs_data:
  def __init__(self,
               antennas=[],fields=[],
               sources=[],observations=[],
               spectral_windows=[],obs_info=None):
    self.antennas = self.gen_antennas(antennas)
    self.sources = self.gen_sources(sources)
    self.fields = self.gen_fields(fields)
    self.observations = self.gen_observations(observations) #/Scans --> broken in listobs parsing :)
    self.spectral_windows = self.gen_spectral_windows(spectral_windows)
    if obs_info:
      self.obs_info = Obs_information(obs_info)

  def gen_spectral_windows(self,obs_spectral_windows):
    """generate a list of Observation objects"""
    spectral_windows = []
    for count in range(len(obs_spectral_windows)):
      spectral_windows.append(Spectral_Windows(obs_spectral_windows[count]))
    return spectral_windows
  
  def gen_observations(self,obs_observations):
    """generate a list of Observation objects"""
    observations = []
    for count in range(len(obs_observations)):
      observations.append(Observations(obs_observations[count]))
    return observations
  
  def gen_sources(self,obs_sources):
    """generate a list of sources objects"""
    sources = []
    for count in range(len(obs_sources)):
      sources.append(Sources(obs_sources[count]))
    return sources
  
  def gen_fields(self,obs_fields):
    """generate a list of fields objects"""
    fields = []
    for count in range(len(obs_fields)):
      field = Fields(obs_fields[count])
      if field.src_id is None:
        self.supplement_srcid(field)
      fields.append(field)
    return fields
  
  def gen_antennas(self,obs_antennas):
    """generate a list of antenna objects"""
    antennas = []
    for count in range(len(obs_antennas)):
      antennas.append(Antenna(obs_antennas[count]))
    return antennas
  
  def supplement_srcid(self,field:Fields):
    for each_source in self.sources:
      if each_source.name == field.name:
        field.src_id = each_source.id

  def to_dict(self):
    summary_dict = {}
    antennas_list=[]
    fields_list=[]
    sources_list=[]
    observations_list=[]
    spectral_windows_list=[]
    
    for count in range(len(self.antennas)):
      antennas_list.append(self.antennas[count].to_dict())
    for count in range(len(self.fields)):
      fields_list.append(self.fields[count].to_dict())
    summary_dict.update({'fields':fields_list})
    for count in range(len(self.sources)):
      sources_list.append(self.sources[count].to_dict())
    for count in range(len(self.observations)):
      observations_list.append(self.observations[count].to_dict())
    for count in range(len(self.spectral_windows)):
      spectral_windows_list.append(self.spectral_windows[count].to_dict())
   
    summary_dict.update({'obs_info':self.obs_info.__dict__}) #already a Dict
    summary_dict.update({'fields':fields_list})
    summary_dict.update({'sources':sources_list})  
    #summary_dict.update({'observations':observations_list})
    summary_dict.update({'spectral_windows':spectral_windows_list})
    #summary_dict.update({'antennas':antennas_list})
    return summary_dict
  