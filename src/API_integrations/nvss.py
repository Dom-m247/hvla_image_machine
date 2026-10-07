"""NVSS (1.4 GHz, dec > -40) sources around a position, from VizieR.

Used to find the bright sources in and around a primary beam that the self-cal model
has to include (image_generation.image_maker.Cleaner.plan_field). Best-effort: a
catalogue that cannot be reached means no outlier fields, said plainly, not a failed run.
"""
from typing import Any, cast

NVSS_CATALOGUE = 'VIII/65/nvss'
VIZIER_TIMEOUT_S = 60


def sources_near(ra_deg, dec_deg, radius_arcmin):
  '''[(ra_deg, dec_deg, flux_jy_at_1.4GHz)] within radius_arcmin, brightest first, or
  None when the catalogue could not be queried.'''
  try:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    vizier = Vizier(columns=['RAJ2000', 'DEJ2000', 'S1.4'], row_limit=-1,
                    timeout=VIZIER_TIMEOUT_S)
    centre = SkyCoord(float(ra_deg) * u.Unit('deg'), float(dec_deg) * u.Unit('deg'))
    found = cast(Any, vizier.query_region(centre, radius=float(radius_arcmin) * u.Unit('arcmin'),
                                          catalog=NVSS_CATALOGUE))
  except Exception as exc:
    print(f"NVSS query failed ({exc}); no outlier fields will be added.")
    return None
  if not found:
    return []
  table = found[0]
  #NVSS positions are sexagesimal strings in J2000
  coords = SkyCoord(table['RAJ2000'], table['DEJ2000'], unit=('hourangle', 'deg'))
  sources = [(float(c.ra.deg), float(c.dec.deg), float(s) / 1e3)
             for c, s in zip(coords, table['S1.4'])]
  return sorted(sources, key=lambda s: -s[2])
