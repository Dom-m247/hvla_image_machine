import casatasks as ct
import re
#from ..pre_calibration import options
import pprint as pp
import math

from pre_calibration.options_class import Options 
from classes.observations_class import Obs_data 
#from ..pre_calibration.options_class import Options 
#from ..pre_calibration.observations_class import Obs_data
#sections to 'parse' : observervation data, spectral Windows, Sources
'''
Why are we parsing listobs? the Returned value doesn't contain everything (i belive) 
also, I already had it mostly done before I had the though to utilize the
return value for listobs()
'''

class parseListObs:
  @staticmethod
  def populate_Obs_data(listObsFile):
    '''
    parses the List_obs File for infomration, which is added to options
      Note: line # are hard coded, see parsing examples if I break
    '''
    #prime realestate to parrallelize in the future
    #try:
    return Obs_data(
        parse_antennas(listObsFile),
        parse_fields(listObsFile),
        parse_sources(listObsFile),
        parse_observations(listObsFile),
        parse_spw(listObsFile),
        parse_obs_info(listObsFile)
      )
      
    #except ValueError as e:
    print(f'An error occured parsing the list_obs {e} section. ')
  
  @staticmethod
  def log_listobs(ms,options):
    '''
    generates a listobs and post to log
      give name of ms w/out .ms
    '''

    ### Listobs
    listobs_file = ms + '-listobs.txt'
    options.split_observations = ct.listobs(vis = ms+'.ms', listfile = listobs_file, overwrite = True)
    read_listobs = open(listobs_file, 'r').read()
    ct.casalog.post(read_listobs)
    return read_listobs
  
  @staticmethod
  def log_listobs_precalib(ms,options):
    '''also utilized to determine solint for t-clean self-cal'''
    listobs_file = ms + '-listobs.txt'
    options.split_observations = ct.listobs(vis = ms+'.ms', listfile = listobs_file, overwrite = True)
    options.solint = getscan_solint(options,options.split_observations)
    read_listobs = open(listobs_file, 'r').read()
    ct.casalog.post(read_listobs)
    return read_listobs

  @staticmethod
  def log_listobs_final_split(ms,options):
    '''make and log a listobs for a given .ms file'''#never used
    listobs_file = ms + '-listobs.txt'
    options.split_observations = ct.listobs(vis = ms, listfile = listobs_file, overwrite = True)
    sol = getscan_solint(options, options.split_observations)
    options.solint = int(sol) if sol is not None else None
    read_listobs = open(listobs_file, 'r').read()
    ct.casalog.post(read_listobs)
    return read_listobs

def parse_obs_info(listobs_text):
  '''Parse observation header info: Observer, Project, Observation type, Data records, etc.'''
  obs_info = {}
  
  # Parse Observer and Project from line: "Observer: XXX     Project: XXX"
  observer_match = re.search(r'Observer:\s*(\S+)', listobs_text)
  if observer_match:
    obs_info['observer'] = observer_match.group(1)
  
  project_match = re.search(r'Project:\s*(\S+)', listobs_text)
  if project_match:
    obs_info['project'] = project_match.group(1)
  
  # Parse Observation type
  observation_match = re.search(r'Observation:\s*(\S+)', listobs_text)
  if observation_match:
    obs_info['observation'] = observation_match.group(1)
  
  # Parse Data records
  data_records_match = re.search(r'Data records:\s*(\d+)', listobs_text)
  if data_records_match:
    obs_info['data_records'] = int(data_records_match.group(1))
  
  # Parse Total elapsed time
  elapsed_time_match = re.search(r'Total elapsed time = ([\d.]+) seconds', listobs_text)
  if elapsed_time_match:
    obs_info['total_elapsed_time'] = float(elapsed_time_match.group(1))
  
  # Parse observation start and end times
  observation_timerange_match = re.search(
    r'Observed from\s+([\d\-/]+/[\d:.]+\.\d+)\s+to\s+([\d\-/]+/[\d:.]+\.\d+)\s+\((\w+)\)',
    listobs_text
  )
  if observation_timerange_match:
    obs_info['observed_from'] = observation_timerange_match.group(1)
    obs_info['observed_to'] = observation_timerange_match.group(2)
    obs_info['time_format'] = observation_timerange_match.group(3)
  return obs_info

def parse_spw(listobs_text):
  '''Parse spectral windows section'''
  # Match from 'Spectral Windows:' through the header line, then capture data until 'Sources:'
  spw_section = re.search(r'Spectral Windows:.*?\n\s*SpwID.*?\n(.*?)(?=Sources:)', listobs_text, re.DOTALL)

  if not spw_section:
    raise ValueError('Spectral Windows')
  
  spws = []
  lines = spw_section.group(1).strip().split('\n')

  for line in lines:
    # Skip empty lines
    if not line.strip():
      continue
    
    # Parse spectral window line - use search instead of match to handle leading whitespace
    match = re.search(
      r'(\d+)\s+(.*?)\s{2,}(\d+)\s+(\w+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([A-Z]{2}(?:\s+[A-Z]{2})*)',
      line
    )
    
    if match:
      # Parse correlations (RR RL LR LL format)
      corrs_str = match.group(9).strip()
      corrs = corrs_str.split()
      
      spw = {
        'id': int(match.group(1)),
        'name': match.group(2).strip(),
        'num_channels': int(match.group(3)),
        'frame': match.group(4),
        'ch0_mhz': float(match.group(5)),
        'chanwid_khz': float(match.group(6)),
        'totbw_khz': float(match.group(7)),
        'ctrfreq_mhz': float(match.group(8)),
        'correlations': corrs
      }
      spws.append(spw)
  
  return spws

def parse_observations(listobs_text):
  '''Parse observations section with scan data.
  Handles both full date+time lines and time-only continuation lines.
  '''
  obs_section = re.search(r'Date\s+Timerange.*?\n(.*?)(?=\(nRows|\n\s*Fields:)', listobs_text, re.DOTALL)
  if not obs_section:
    raise ValueError('Observations')

  # Lines with full date prefix: "DD-Mon-YYYY/HH:MM:SS.s - HH:MM:SS.s  scan fld name nrows [spw] [intv]"
  FULL_RE = re.compile(
    r'(\d{2}-\w+-\d{4})/(\d{2}:\d{2}:\d{2}\.\d+)\s*-\s*(\d{2}:\d{2}:\d{2}\.\d+)\s+'
    r'(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\[[\d,\s]+\])\s+(\[[\d,\s]+\])'
  )
  # Continuation lines with time only (date carried forward from previous full line)
  TIME_RE = re.compile(
    r'(\d{2}:\d{2}:\d{2}\.\d+)\s*-\s*(\d{2}:\d{2}:\d{2}\.\d+)\s+'
    r'(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\[[\d,\s]+\])\s+(\[[\d,\s]+\])'
  )

  observations = []
  current_date = None

  for line in obs_section.group(1).split('\n'):
    stripped = line.strip()
    if not stripped:
      continue

    m = FULL_RE.search(stripped)
    if m:
      current_date = m.group(1)
      observations.append({
        'date': current_date,
        'timerange_start': m.group(2),
        'timerange_end': m.group(3),
        'scan': int(m.group(4)),
        'field_id': int(m.group(5)),
        'field_name': m.group(6),
        'nrows': int(m.group(7)),
        'spw_ids': m.group(8),
        'average_intervals': m.group(9),
      })
      continue

    if current_date:
      m = TIME_RE.search(stripped)
      if m:
        observations.append({
          'date': current_date,
          'timerange_start': m.group(1),
          'timerange_end': m.group(2),
          'scan': int(m.group(3)),
          'field_id': int(m.group(4)),
          'field_name': m.group(5),
          'nrows': int(m.group(6)),
          'spw_ids': m.group(7),
          'average_intervals': m.group(8),
        })

  return observations

def parse_sources(listobs_text):
  '''Parse sources section'''
  sources_section = re.search(r'Sources: \d+(.*?)(?=\n\n|Antennas|\Z)', listobs_text, re.DOTALL)
  if not sources_section:
    raise ValueError('Sources')
  
  sources = []
  lines = sources_section.group(1).strip().split('\n')

  for line in lines:
    # Skip header lines and empty lines
    if not line.strip() or 'ID' in line:
      continue
    parts = line.split()
    # Sources line format:
    # Parts: [0]ID [1]Name [2]SpwID [3]RestFreq [4]SysVel
    if len(parts) >= 5:
      source = {
        'id': int(parts[0]),
        'name': parts[1],
        'SpwId': parts[2],
        'RestFreq': float(parts[3]),
        'SysVel': float(parts[4]),  
      }
      sources.append(source)
  return sources

def parse_fields(listobs_text):
  '''Parse fields section, handling empty Code field and long epoch names'''
  fields_section = re.search(r'Fields: \d+(.*?)(?=\n\n|Spectral|\Z)', listobs_text, re.DOTALL)
  if not fields_section:
    raise ValueError('fields')
  
  fields = []
  lines = fields_section.group(1).strip().split('\n')
  
  for line in lines:
    if not line.strip() or 'ID' in line:
      continue
    
    # Use regex to parse: ID [Code] Name RA Decl Epoch SrcId nRows
    # Code is optional (single letter or empty)
    # Epoch can contain letters, numbers, and underscores (e.g., B1950_VLA0, J2000)
    match = re.match(r'\s*(\d+)\s+([A-Z]?)\s+(\S+)\s+([\d:.]+)\s+([\d+\-.]+)\s+([\w_]+)\s+(\d+)(?:\s+(\d+))?', line)
    if match:
      # Handle case where SrcId and nRows might both be present or just nRows
      src_id = int(match.group(7))
      nrows = int(match.group(8)) if match.group(8) else int(match.group(7))
      
      field = {
        'id': int(match.group(1)),
        'code': match.group(2) if match.group(2) else None,  # None if empty
        'name': match.group(3),
        'ra': match.group(4),
        'decl': match.group(5),
        'epoch': match.group(6),
        'src_id': src_id if match.group(8) else None,
        'nrows': nrows
      }
      fields.append(field)
  return fields

def parse_antennas(listobs_text):
  '''Parse antenna data from listobs output'''
  # Find the Antennas section
  antenna_section = re.search(r'Antennas: \d+:(.*?)(?=\n\n|\Z)', listobs_text, re.DOTALL)
  if not antenna_section:
    raise ValueError('Antennas')
  
  antennas = []
  lines = antenna_section.group(1).strip().split('\n')
  
  for line in lines:
    # Skip header lines and empty lines
    if not line.strip() or 'ID' in line or 'ITRF' in line or 'East' in line:
      continue
    parts = line.split()
    # Antenna line format: ID Name Station Diameter Long Lat East North Elev X Y Z
    # Parts: [0]ID [1]Name [2]Station [3]Diam [4]Long [5]Lat [6]East [7]North [8]Elev [9]X [10]Y [11]Z
    if len(parts) >= 10:
      antenna = {
        'id': int(parts[0]),
        'name': parts[1],
        'station': parts[2],
        'diameter': parts[3], #parts[4] = m for meters
        'longitude': parts[5],  # Keep as string (DMS format)
        'latitude': parts[6],   # Keep as string (DMS format)
        'east_offset': float(parts[7]),
        'north_offset': float(parts[8]),
        'elevation': float(parts[9]),
        'x': float(parts[10]) if len(parts) > 10 else None,
        'y': float(parts[11]) if len(parts) > 11 else None,
        'z': float(parts[12]) if len(parts) > 12 else None,
      }
      antennas.append(antenna)
  return antennas

def antennas_distance(options:Options):
  """calculate and sort antenna distances"""
  antennas:list = options.observation_data.antennas
  bestdistance = 1000000
  distance_list = []
  for antenna in antennas:
    distance = math.sqrt(pow(antenna.east_offset,2)+pow(antenna.north_offset,2))
    pair = {'id': antenna.name, 'distance': distance}
    distance_list.append(pair)
    if distance < bestdistance:
      bestdistance = distance
  return sorted(distance_list, key=lambda x: x['distance'])
  #stuff?

def check_integration_time_sameness(array):
  """check if all scans have the same integration time, if not, return False"""
  first_int_time = array[0]
  #for int_time in array:
  #  if int_time != first_int_time:
  #    raise ValueError(f"Integration times are not the same across scans! Found {int_time} and {first_int_time}")

def getscan_solint(options:Options,listobs_dict):
  """get integration time of source from listobs output
    throws exception if integration times are not the same across scans
  """
  ## options.split_observations-> 'scan_##' -> scan_solint
  #scan_solint_array = []
  #numScans = 0
  solint = None
  for each_key in listobs_dict:
    if 'scan' in each_key:
      for each_subsection in listobs_dict[each_key]['0']:
        if each_subsection == 'FieldName':
          if listobs_dict[each_key]['0'][each_subsection] == options.source or listobs_dict[each_key]['0'][each_subsection] == options.source_ids.listobs_name:
            solint = listobs_dict[each_key]['0']['IntegrationTime']
            return solint
        #if each_subsection == 'IntegrationTime':
        #  intTime =  listobs_dict[each_key]['0'][each_subsection]
        #  scan_solint_array.append(intTime)
        #  numScans += 1 
  
  #check_integration_time_sameness(scan_solint_array)
  #solint = sum(scan_solint_array)/numScans
  return solint
  #return 30 
