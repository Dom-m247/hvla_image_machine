'''Offline tests of pipeline helpers (listobs parsing, measurement bookkeeping, harness
tables). Puts src/ on the path; nothing here runs a CASA task on data.
Run from the repo root: python -m unittest'''
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
