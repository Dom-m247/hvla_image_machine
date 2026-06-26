from astroquery.ipac.ned import Ned
from classes.constants import BAND_MHZ_RANGES, MIN_FLUX_FOR_SELF_CAL
from pprint import pp
from requests.exceptions import Timeout, ConnectionError
from typing import Any, cast


class NED_API:
  '''functions for NED integration'''
  @staticmethod
  def obj_exists(source_name):
    """
    Query NED to check a source exists under name
    """
    ned = Ned()
    try:
      ned.TIMEOUT = 10  # seconds
      #astroquery is untyped: query_object returns an astropy Table at runtime
      query = cast(Any, ned.query_object(object_name=source_name))
      if len(query) == 1:
        ra = float(query['RA'])
        decl = float(query['DEC'])
        #Redshift check here?
        ra_decl = {"ra": ra, "decl": decl}
        result = {'ra_decl':ra_decl, 'alias':str(query[0]['Object Name'])}
        return result
      else:
        return False
    except (Timeout, ConnectionError) as e:
        print(f"NED timeout or connection error: {e}")
        return False
    except Exception as e:
      print(f"Error occurred while querying NED: {e}")
      return False
    
  @staticmethod
  def get_photometry(source_name):
    """
    Query NED for photometry table, with one retry on failure.
    """
    print("Querying NED for source table")
    ned = Ned()
    for attempt in range(2):
      try:
        #astroquery is untyped: get_table returns an astropy Table at runtime
        result = cast(Any, ned.get_table(object_name=source_name, table='photometry'))
        return result
      except Exception as e:
        if attempt == 0:
          print(f"Photometry query failed, retrying... ({e})")
        else:
          print(f"Error occurred while querying NED for Photometry: {e}")
    return False

  @staticmethod
  def do_photonometry_check(source_name, band, alias=None):
    print("Checking self-calibration potential")
    photometry_table = NED_API.get_photometry(source_name)

    if not photometry_table and alias and alias != source_name:
      print(f"Retrying photometry query with NED alias: {alias}")
      photometry_table = NED_API.get_photometry(alias)

    if not photometry_table:
      return False

    band_range_low = (BAND_MHZ_RANGES[band][0] * 1e6) #- ((BAND_MHZ_RANGES[band][0] * 1e6)*0.2) #20% below the lower end of the band
    band_range_high = (BAND_MHZ_RANGES[band][1] * 1e6) #+ ((BAND_MHZ_RANGES[band][1] * 1e6)*0.2) #20% above the upper end of the band

    for row in range(len(photometry_table)):
      freq = photometry_table[row]['Frequency']
      flux = photometry_table[row]['Flux Density']
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
      alias = ned_result.get('alias')
      if is_Self_Calable := NED_API.do_photonometry_check(source_name, band, alias=alias):
        return is_Self_Calable

    return False
    