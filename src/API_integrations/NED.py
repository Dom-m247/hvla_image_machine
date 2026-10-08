from API_integrations.catalog_client import ned_lookup, ned_photometry
from classes.constants import BAND_MHZ_RANGES, MIN_FLUX_FOR_SELF_CAL
from pprint import pp


class NED_API:
  '''functions for NED integration'''
  @staticmethod
  def obj_exists(source_name):
    """
    Query NED to check a source exists under name
    """
    try:
      found = ned_lookup(source_name)
    except Exception as e:
      print(f"Error occurred while querying NED: {e}")
      return False
    if found is None:
      return False
    ra_decl = {"ra": found['ra'], "decl": found['dec']}
    return {'ra_decl': ra_decl, 'alias': found['name'],
            'redshift': '' if found['redshift'] is None else found['redshift']}

  @staticmethod
  def get_photometry(source_name):
    """
    Query NED for photometry: [freq_hz, flux_jy] rows, or False when there are none.
    """
    print("Querying NED for source table")
    try:
      return ned_photometry(source_name) or False
    except Exception as e:
      print(f"Error occurred while querying NED for Photometry: {e}")
      return False

  @staticmethod
  def do_photonometry_check(source_name, band):
    print("Checking self-calibration potential")
    photometry_table = NED_API.get_photometry(source_name)

    if not photometry_table:
      return False

    band_range_low = (BAND_MHZ_RANGES[band][0] * 1e6) #- ((BAND_MHZ_RANGES[band][0] * 1e6)*0.2) #20% below the lower end of the band
    band_range_high = (BAND_MHZ_RANGES[band][1] * 1e6) #+ ((BAND_MHZ_RANGES[band][1] * 1e6)*0.2) #20% above the upper end of the band

    for freq, flux in photometry_table:
      if (band_range_low) <= freq <= (band_range_high):
        if flux >= MIN_FLUX_FOR_SELF_CAL:
          #Source has potential for self-calibration with flux 
          return True
    #Source does not have potential for self-calibration in band 
    return False
  

  @staticmethod
  def check_self_cal_potential(source_name,band):
    """
    Check if a source has potential for self-calibration based on its photometry and the band of observation
    This is a very rough check based on the flux density at the relevant frequencies for the band
    """
    ned_result = NED_API.obj_exists(source_name)
    if ned_result is not False:
      if is_Self_Calable := NED_API.do_photonometry_check(source_name, band):
        return is_Self_Calable

    return False
    