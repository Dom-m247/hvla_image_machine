#for doing a RADIO_SEARCH based Download
from classes.CLI_input import CLI
from pre_calibration.options_class import Options
import subprocess
from pprint import pp
import re
import paramiko
import getpass
import pprint
from pathlib import Path


class nrao_observeration:
    """
    Class to handle NRAO observations. 
    """
    FIELDS = ['date', 'proj_code', 'seg', 'band', 'cfg', 'resln',
               'las', 'frequency', 'bandwidth', 'time', 'nants',
               'sensitivity', 'nscans_hours', 'separation', 'name']

    def __init__(self, fields):
        #Date      |ProjCode  |Seg    |Band |Cfg |Resln	|LAS	|Frequency	|Bandwidth	|Time	|NAnts	|Sensitivity	|Nscans/Hours	|Separation	|Name
        for attr, value in zip(self.FIELDS, fields):
            setattr(self, attr, value)

    def __repr__(self):
        return f"{self.__dict__}"


class nrao_archfile:
    """
    Class to represent a single archive file entry from --archfileinfo output.
    """
    def __init__(self, file_number, file_name, band, date, start, size):
        self.file_number = file_number
        self.file_name = file_name
        self.band = band
        self.date = date
        self.start = start
        self.size = size

    def __repr__(self):
        return f"{self.__dict__}"


class nrao_segment:
    """
    Class to represent a segment from --archfileinfo output.
    Contains a segment name and a list of nrao_archfile objects.
    """
    def __init__(self, name, files):
        self.name = name
        self.files = files

    def __repr__(self):
        return f"Segment {self.name}: {self.files}"


class RadioSearch2:
    """
    Persistent SSH connection for multiple radio_search2 calls.
    
    Usage:
        with RadioSearch2() as rs:
            result1 = rs('4C35.03', 'BANDS', 'C')
            result2 = rs('--archfileinfo', '13B-326')
            result3 = rs('3C273', 'BANDS', 'X', 'CONF', 'A')
    """
    def __init__(self, host, user, password=None, key_filename=None):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_kwargs = {"hostname": host, "username": user}
        if key_filename:
            connect_kwargs["key_filename"] = key_filename
        elif password:
            connect_kwargs["password"] = password
        else:
            connect_kwargs["password"] = getpass.getpass(f"{user}@{host} password: ")
        
        self.client.connect(**connect_kwargs)
    
    def __call__(self, *args):
        quoted_args = " ".join(f"'{a}'" for a in args)
        remote_cmd = (
            "cd REDACTED_PATH "
            f"&& ./radio_search2 {quoted_args}"
        )
        
        stdin, stdout, stderr = self.client.exec_command(remote_cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        
        if err:
            print(f"radio_search2 stderr:\n{err}")
        
        return out
    
    def __enter__(self):
        return self
    
    def __exit__(self, *exc):
        self.client.close()


def parseArchFileInfo(results):
    """
    Parse the output of radio_search2 --archfileinfo into a list of nrao_segment objects.
    """
    segments = []
    current_segment_name = None
    current_files = []

    for line in results.splitlines():
        seg_match = re.match(r'^Segment\s+(\S+)', line)
        if seg_match:
            if current_segment_name is not None:
                segments.append(nrao_segment(current_segment_name, current_files))
            current_segment_name = seg_match.group(1)
            current_files = []
            continue
        if line.startswith('---') or not line.strip():
            continue
        if '#' in line and 'File' in line and 'Start' in line:
            continue
        parts = line.split()
        if not parts or not parts[0].isdigit():
            continue
        # parts: [file_number, file_name, band, date, time, size]
        file_number = int(parts[0])
        file_name = parts[1]
        band = parts[2]
        date = parts[3]
        start = parts[4]
        size = parts[5]
        current_files.append(nrao_archfile(file_number, file_name, band, date, start, size))

    if current_segment_name is not None:
        segments.append(nrao_segment(current_segment_name, current_files))

    return segments


def parseObservations(results):
    """
    Parse the output of radio_search2 into a list of nrao_observeration objects.
    """
    observations = []
    separator_count = 0
    in_data = False
    for line in results.splitlines():
        if line.startswith('---'):
            separator_count += 1
            if separator_count >= 2:
                in_data = True
            continue
        if not in_data or not line.strip():
            continue
        if line.strip().lower() == 'done.':
            break
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 15:
            continue
        if parts[0].lower() == 'date':
            continue
        if parts[1].upper() == 'SYSTEM':
            continue
        observations.append(nrao_observeration(parts[:15]))
    return observations



class RadioSearchIntegration:
  """Class to handle integration of radio_search into the HVLA Image Machine workflow."""

  def perform_radio_search(options:Options):
    """Perform the radio search and download archives based on user input."""
    # This is a placeholder for the actual implementation of the radio search.
    # You would need to implement the logic to interact with the radio search tool,
    # process the results, and download the relevant archives.
    CLI.getSourceInfo(options)
    #DO radio_search with options.source and options.band

    password_file = Path(__file__).resolve().with_name('nraoCreds.txt')
    if not password_file.exists():
        raise FileNotFoundError(f"Password file not found: {password_file}")
    creds = {}
    with open(password_file, 'r') as pwrd_file:
        for line in pwrd_file:
            line = line.strip()
            if '=' in line:
                key, _, val = line.partition('=')
                creds[key.strip()] = val.strip()
    for key in ('host', 'user', 'password'):
        if not creds.get(key):
            raise ValueError(f"Missing or empty '{key}' in credentials file.")
    with RadioSearch2(host=creds['host'], user=creds['user'], password=creds['password']) as rs:
        rs_results = rs(options.search_alias, 'BANDS', options.band)


    # Example: Call a function from the radio_search module to execute the search
    # results = radio_search.execute_search(self.source.sysArgs)
    # Process results and download archives as needed

  def find_ssh_pw():
    return 'nraoPWD_DONOTLETGITTRACKME.txt'
