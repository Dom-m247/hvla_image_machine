"""The one place that reaches into the pipeline's own modules.

Importing src/ is not free -- options_class pulls in casatasks -- and the import
path has to be set up before any of it resolves, so both the path fix-up and the
re-exports live here rather than being repeated in every harness module.

Everything the harness does with archives, sources and observations goes through
these symbols, so the harness tests the shipping code paths instead of a
parallel implementation that can drift away from them.
"""
import sys
from pathlib import Path

#<repo>/harnesses/harness/pipeline.py -> <repo>/src, which has to be importable
#before anything below resolves
SRC = Path(__file__).resolve().parents[2] / 'src'
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

#--- pipeline modules (import order matters only in that SRC must be on the path) ---
from API_integrations.NED import NED_API                      # noqa: E402
from archive_dowload.radio_search_integration import (        # noqa: E402
  DelosDownload, RadioSearchIntegration, parseArchFileInfo, sensitivity_jy, size_mb,
)
from classes import creds                                     # noqa: E402
from classes.CLI_input import CLI                             # noqa: E402
from classes.image_data import first_value, imstat_dict       # noqa: E402
from classes.constants import (                               # noqa: E402
  AUTO, BAND_GHZ_RANGES, DECISIONS, DEFAULT_IMAGE_SIZE, FLAG_METHODS_DEFAULT,
  FOLDER_NAME, FORCE, IMPORT_JSON, MIN_SNR, MS_SUB_PATH, OFF, CLEAN_ROBUST,
)
from pre_calibration.import_settings import revmove_path      # noqa: E402
from pre_calibration.options_class import Options             # noqa: E402

#the project's own resolver owns where the root is; the harness does not get a
#second opinion on it
REPO_ROOT = creds.project_root()

#the pipeline entry point the harness drives, and the interpreter that can run it
MAIN_SCRIPT = SRC / 'HVLA_image_machine.py'
VENV_PYTHON = REPO_ROOT / '.hvla_env' / 'bin' / 'python'

#Pre-EVLA cutoff. CLI already owns this year -- it is what the interactive
#observation table paints red -- so the harness borrows it rather than declaring
#a second, driftable copy of the same fact.
PRE_EVLA_YEAR = CLI.RADIO_SEARCH_HIGHLIGHT_YEAR

__all__ = [
  'AUTO', 'BAND_GHZ_RANGES', 'CLEAN_ROBUST', 'CLI', 'DECISIONS',
  'DEFAULT_IMAGE_SIZE', 'DelosDownload', 'FLAG_METHODS_DEFAULT', 'FOLDER_NAME', 'FORCE',
  'IMPORT_JSON', 'MAIN_SCRIPT', 'MIN_SNR', 'MS_SUB_PATH', 'NED_API', 'OFF',
  'first_value', 'imstat_dict',
  'Options', 'PRE_EVLA_YEAR', 'REPO_ROOT', 'RadioSearchIntegration', 'SRC',
  'VENV_PYTHON', 'creds', 'parseArchFileInfo', 'revmove_path', 'sensitivity_jy',
  'size_mb',
]


def delocalize(path):
  """A local archive path in the form import.json stores it (<FOLDER_NAME>/...).

  import_settings.revmove_path does the slicing; this adds the check it lacks.
  A path outside the project slices to a one-character string rather than
  failing, which surfaces three stages later as an unreadable archive.
  """
  text = str(path)
  if FOLDER_NAME not in text:
    raise ValueError(
      f"archive path {text!r} is not under '{FOLDER_NAME}/'; import.json stores "
      f"paths relative to the project folder and cannot address it.")
  return revmove_path(text)
