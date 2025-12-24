FULLMS = 'fullSet' #+".ms"
import casatasks as ct
import sys,os
import re
from data_class import data
import pprint as pp
import math 

def parseListObs(listObsFile,options:data):
  """parses the List_obs File for infomration, which is added to options
    Note: line # are hard coded, see parsing examples if I break
  """
  antenna_dict = {'antennas',parse_antennas(listObsFile)}
  options.add_dict(antenna_dict)
  fields_dict = {'fields',parse_fields(listObsFile)}
  options.add_dict(fields_dict)


def parse_fields(listobs_text):
  """Parse fields section, handling empty Code field"""
  fields_section = re.search(r'Fields: \d+(.*?)(?=\n\n|Spectral|\Z)', listobs_text, re.DOTALL)
  if not fields_section:
    return []
  
  fields = []
  lines = fields_section.group(1).strip().split('\n')
  
  for line in lines:
    if not line.strip() or 'ID' in line:
      continue
    
    # Use regex to parse: ID [Code] Name RA Decl Epoch SrcId nRows
    # Code is optional (single letter or empty)
    match = re.match(r'\s*(\d+)\s+([A-Z]?)\s+(\S+)\s+([\d:.]+)\s+([\d+\-.]+)\s+(\w+)\s+(\d+)\s+(\d+)', line)
    if match:
      field = {
        'id': int(match.group(1)),
        'code': match.group(2) if match.group(2) else None,  # None if empty
        'name': match.group(3),
        'ra': match.group(4),
        'decl': match.group(5),
        'epoch': match.group(6),
        'src_id': int(match.group(7)),
        'nrows': int(match.group(8))
      }
      fields.append(field)
  pp.pprint(fields)
  return fields

def parse_antennas(listobs_text):
  """Parse antenna data from listobs output"""
  # Find the Antennas section
  antenna_section = re.search(r'Antennas: \d+:(.*?)(?=\n\n|\Z)', listobs_text, re.DOTALL)
  if not antenna_section:
    return []
  
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

def antennas_distance(antennas):
  #calculate and sort antenna_distances, Proably not necessy
  bestdistance = 1000000
  distance_list = []
  for antenna in antennas:
    distance = math.sqrt(pow(antenna['east_offset'],2)+pow(antenna['north_offset'],2))
    pair = {'id': antenna['id'], 'distance': distance}
    distance_list.append(pair)
    if distance < bestdistance:
      bestdistance = distance
      print(f"New Best Distance! antenna {antenna['id']} at {bestdistance}")
  distance_list_sorted = sorted(distance_list, key=lambda x: x['distance'])
  pp.pprint(distance_list_sorted)

def log_listobs(ms):
  """generates a listobs and post to log
      give name of ms w/out .ms"""
  import pprint as pp
  ### Listobs
  listobs_file = ms + "-list-file.txt"
  ct.listobs(vis = ms+".ms", listfile = listobs_file, overwrite = True)
  read_listobs = open(listobs_file, 'r').read()
  ct.casalog.post(read_listobs)
  return read_listobs

def convert_to_ms(archive):
  """
  Converts raw HVLA data archive to Measurement Set (MS) format
  """
  #OUTPUT MS name = "fullMS.ms" -> weird cstring error if not directly entered.
  FULLMS = 'fullSet'
  if (archive.endswith('.ms')):
    print(f"Archive {archive} is already in MS format.")
    return
  #import archive to MS
  print(f"Converting archive {archive} to Measurement Set format...")
  try:
    if not os.path.exists(FULLMS+'.ms'):
      ct.importvla(archivefiles={archive},vis=FULLMS+'.ms')
    return log_listobs(FULLMS)

  except RuntimeError as file_exists:
    print(f"Vis file already exists, delete it and re-run")
    sys.exit() # add call to a cleanup script?
    

def data_cal(options:data):
  """
  main in for data calibration of HVLA data archive
  Creates MS files from raw data, applies calibration
  """
  list_obs = convert_to_ms(options.archive_file)
  parseListObs(list_obs,options)



if __name__ == "__main__":
  #test run
  options = data()
  testinput = {'archive_file': "/home/dominic/hvla_script_proj/data_archive/AL727/observation.54757.0577199/AL727_1_54757.05772_54757.55622.exp"}
  options.add_dict(testinput)
  data_cal(options)