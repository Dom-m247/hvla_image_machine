'''Offline tests of the imaging helpers. Puts src/ on the path; nothing here runs tclean.
Run from the repo root: python -m unittest tests.imaging.test_outlier_fields'''
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
