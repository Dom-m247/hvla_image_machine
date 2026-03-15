import json
import os


class CalibratorEntry:
  """Wraps a single calibrator JSON entry with convenient attribute access."""
  def __init__(self, data: dict):
    j = data.get('j2000', {})
    b = data.get('b1950', {})
    self.iau_name        = j.get('iau_name')
    self.alt_name        = j.get('alt_name')
    self.equinox         = j.get('equinox')
    self.position_quality = j.get('position_quality')
    self.ra              = j.get('ra')
    self.dec             = j.get('dec')
    self.position_reference = j.get('position_reference')
    self.bands           = data.get('bands', [])
    self.b1950_iau_name  = b.get('iau_name')
    self.b1950_ra        = b.get('ra')
    self.b1950_dec       = b.get('dec')
    self._raw            = data

  def get_band(self, band_code):
    """Return the band dict for the given band code, or None."""
    for band in self.bands:
      if band.get('band_code') == band_code:
        return band
    return None

  def flux_for_band(self, band_code):
    """Return flux in Jy for the given band code, or None."""
    band = self.get_band(band_code)
    return band.get('flux_Jy') if band else None

  def __repr__(self):
    return f"CalibratorEntry(iau_name={self.iau_name!r}, alt_name={self.alt_name!r}, ra={self.ra!r}, dec={self.dec!r})"


class NRAOCalibrators:
  JSON_PATH = os.path.join(os.path.dirname(__file__), '..', 'data_calibration', 'nrao_calibrators.json')

  def __init__(self):
    with open(self.JSON_PATH, 'r') as f:
      raw = json.load(f)
    self.calibrators = [CalibratorEntry(entry) for entry in raw if entry]

  def find_by_name(self, name) -> CalibratorEntry | None:
    """Return a CalibratorEntry whose iau_name or alt_name matches (J2000 or B1950)."""
    name = name.strip()
    for cal in self.calibrators:
      if name in (cal.iau_name, cal.alt_name, cal.b1950_iau_name):
        return cal
    return None

  def find_by_band(self, band_code) -> list[CalibratorEntry]:
    """Return all CalibratorEntry objects that have data for the given band code."""
    return [cal for cal in self.calibrators if cal.get_band(band_code) is not None]

  def get_ra_dec(self, cal: CalibratorEntry):
    """Return (ra, dec) strings from the J2000 block."""
    return cal.ra, cal.dec
