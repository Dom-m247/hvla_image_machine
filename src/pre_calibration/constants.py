#parent directory name, edit if different!
FOLDER_NAME = 'hvla_image_machine'
IMPORT_JSON = 'import.json'
#Measurment set Name Defaults
FULLMS = 'fullset' # for the full MS before splitting
AMP_CAL_MS = 'initial' #'amp_cal_set'
#GAINCAL_G0ALL = AMP_CAL_MS + '.G0all'
#BANDPASS_B0 = AMP_CAL_MS + '.B0'
#GAINCAL_G1 = AMP_CAL_MS + '.G1'
#FLUXSCALE_X = AMP_CAL_MS + '.fluxscale' # + '1','2' ..etc
#CALIBRATED_MS = 'source' #final calibrated ms for imaging
#
#GAINCAL_G2 = AMP_CAL_MS +'.G2'

GAINCAL_G0ALL =  '.G0all'
BANDPASS_B0 = '.B0'
GAINCAL_G1 = '.G1'
FLUXSCALE_X = '.fluxscale' # + '1','2' ..etc
CALIBRATED_MS = 'source' #final calibrated ms for imaging

GAINCAL_G2 = '.G2'
SELF_CAL= '.selfcal'

#temp not utlizied / fallbacks
DEFAULT_IMAGE_SIZE = [1080,1080] # keep me a perfect Square!
INITIAL_NITER = 250 # half of niter from tutorial
MIN_SNR = 5.0 #a default min SNR for gaincal
FIRST_IMAGE = 'image'

#class Band:
  #band name, GHZ range, MHZ range, Angular res, Solint?
#calibration source type 
TYPE_FLUX_CAL = 'flux_calibrator'
TYPE_PHASE_CAL = 'phase_cal'
TYPE_TARGET = 'target'
AUTO = 'auto'
  
#Constants that may be integrated, but are being placed here for reference!
BAND_GHZ_RANGES = {'L': [0.985, 2.025], 
                   'S': [2.026, 4.013], 
                   'C': [4.309, 7.461], 
                   'X': [8.000, 11.512], 
                   'Ku': [13.133, 18.000], 
                   'K': [20.000, 26.412], 
                   'Ka': [28.258, 37.011], 
                   'Q': [43.148, 48.873]}
BAND_MHZ_RANGES = {'L': [985.0, 2025.0], 
                   'S': [2026.0, 4013.0], 
                   'C': [4309.0, 7461.0], 
                   'X': [8000.0, 11512.0], 
                   'Ku': [13133.0, 18000.0], 
                   'K': [20000.0, 26412.0], 
                   'Ka': [28258.0, 37011.0], 
                   'Q': [43148.0, 48873.0],}
#note: configurations A=0,B=1,C=2,D=3
BAND_ANGULAR_RESOLUTION = {'4': [24,80,260,850],
                           'P': [5.6,18.5,60,200],
                           'L': [1.3,4.3,14,46],
                           'S': [0.65,2.1,7.0,23],
                           'C': [0.33,1.0,3.5,12],
                           'X': [0.20,0.60,2.1,7.2],
                           'Ku':[0.13,0.42,1.4,4.6],
                           'K': [0.089,0.28,0.95,3.1],
                           'Ka':[0.059,0.19,0.63,2.1],
                           'Q': [0.043,0.14,0.47,1.5]
}
BAND_LARGEST_SCALE = {'4': [800,2200,20000,20000],
                           'P': [155,515,4150,4150],
                           'L': [36,120,970,970],
                           'S': [18,58,490,490],
                           'C': [9.9,29,240,240],
                           'X': [5.3,17,145,145],
                           'Ku':[3.6,12,97,97],
                           'K': [2.4,7.9,66,66],
                           'Ka':[1.6,5.3,44,44],
                           'Q': [1.2,3.9,32,32]
}
ARRAY_CONFIGURATION = 1

BAND_SOLINT = {'4':'900', 'P':'900', 'L':'450', 'S':'450', 'C':'240', 'X':'240', 'Ku':'180', 'U':'180', 'K':'120', 'Ka':'90', 'Q':'60'}

COMMON_AMPCALS_DICT = {'1331+305': '3C286', 
                      '1328+307': '3C286', 
                      '0542+4951': '3C147', 
                      '0137+3309': '3C48', 
                      '0134+329': '3C48', 
                      '0137+331': '3C48', 
                      '0521+1638': '3C138'} #upgrade with calibrator list, and pull flux data for 'custom' callibrators


#defunct
EXPORT_KEYS = ['source','archive_file', 'band', 'breakpoints', 
               'solint','custom_amp_cal', 'reference_antenna', 
               'amp_cal_source','model'] #amp_cal_source + model import not supported (over written)



