#parent directory name, edit if different!
FOLDER_NAME = "hvla_script_proj"

#Measurment set Names
FULLMS = 'fullSet' # for the full MS before splitting
AMP_CAL_MS = 'init' #'amp_cal_set'

#Constants that may be integrated, but are being placed here for reference!
BAND_GHZ_RANGES = {'L': [0.985, 2.025], 
                   'S': [2.026, 4.013], 
                   'C': [4.309, 7.461], 
                   'X': [8.000, 11.512], 
                   'Ku': [13.133, 18.000], 
                   'K': [20.000, 26.412], 
                   'Ka': [28.258, 37.011], 
                   'Q': [43.148, 48.873]}
BAND_MHZ_RANGES = {"L": [985.0, 2025.0], 
                   "S": [2026.0, 4013.0], 
                   "C": [4309.0, 7461.0], 
                   "X": [8000.0, 11512.0], 
                   "Ku": [13133.0, 18000.0], 
                   "K": [20000.0, 26412.0], 
                   "Ka": [28258.0, 37011.0], 
                   "Q": [43148.0, 48873.0],}


COMMON_AMPCALS_DICT = {'1331+305': '3C286', 
                      '1328+307': '3C286', 
                      '0542+4951': '3C147', 
                      '0137+3309': '3C48', 
                      '0134+329': '3C48', 
                      '0137+331': '3C48', 
                      '0521+1638': '3C138'} #upgrade with calibrator list, and pull flux data for "custom" callibrators

EXPORT_KEYS = ["source","archive_file", "band", "breakpoints", 
               "solint","custom_amp_cal", "reference_antenna", 
               "amp_cal_source","model"] #amp_cal_source + model import not supported (over written)



