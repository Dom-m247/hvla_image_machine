"""The project's credentials file -- one reader, one location.

Credentials live in a single Creds.json at the project root, and this module is
the only thing that knows where. Every reader goes through here: a location
resolved per-module drifts, and two modules reading different files report no
error at all.

Stdlib-only (plus constants), so a caller needing one value out of a JSON file
does not inherit a heavier module's import chain to get it.

    from classes import creds
    values = creds.load(required=('some_key',))
"""
import json
from pathlib import Path

from classes.constants import FOLDER_NAME

CREDS_FILE = 'Creds.json'  #project-wide credentials, at the project root


def project_root():
  """The hvla_image_machine project root, from this file's path.

  Walk up looking for FOLDER_NAME, falling back to the known depth
  (<root>/src/classes/<file>). Lifted here from DelosDownload._repo_root so the
  path logic has one home rather than one per module that needs it.
  """
  here = Path(__file__).resolve()
  for parent in here.parents:
    if parent.name == FOLDER_NAME:
      return parent
  return here.parents[2]  #<root>/src/classes/<file> -> <root>


def path():
  """The credentials file. Raises FileNotFoundError if it is not there."""
  creds_path = project_root() / CREDS_FILE
  if not creds_path.is_file():
    raise FileNotFoundError(f"Credentials file not found: {creds_path}")
  return creds_path


def load(required=()):
  """Load the credentials as a dict, checking `required` keys are non-empty.

  `required` defaults to nothing on purpose: this file is shared between
  unrelated services now, so no set of keys is universally mandatory. Each
  caller states what it needs, and gets an error naming the key it is missing
  rather than a KeyError three frames later.
  """
  creds_path = path()
  try:
    with open(creds_path, 'r') as creds_file:
      creds = json.load(creds_file)
  except json.JSONDecodeError as err:
    raise ValueError(f"Credentials file {creds_path} is not valid JSON: {err}")
  for key in required:
    if not creds.get(key):
      raise ValueError(f"Missing or empty '{key}' in credentials file {creds_path}.")
  return creds
