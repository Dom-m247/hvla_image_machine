'''Offline tests of the NED/SIMBAD client. Importing this package puts src/ on the path and
points any real HTTP at a dead proxy, so nothing here can reach NED or SIMBAD.
Run from the repo root: python -m unittest'''
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

os.environ.pop('NO_PROXY', None)
os.environ.pop('no_proxy', None)
for var in ('HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY'):
  os.environ[var] = os.environ[var.lower()] = 'http://127.0.0.1:9'
