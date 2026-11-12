'''Offline tests of the harness. Puts harnesses/ on the path; nothing here searches the
archive or runs the pipeline. Run from the repo root: python -m unittest'''
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'harnesses'))
