#parent directory name, edit if different!
FOLDER_NAME = 'hvla_image_machine'
IMPORT_JSON = 'import.json'
#Measurment set Names
FULLMS = 'fullSet' # for the full MS before splitting
AMP_CAL_MS = 'init' #'amp_cal_set'
GAINCAL_G0ALL = AMP_CAL_MS + '.G0all'
BANDPASS_B0 = AMP_CAL_MS + '.B0'
GAINCAL_G1 = AMP_CAL_MS + '.G1'
FLUXSCALE_X = AMP_CAL_MS + '.fluxscale' # + '1','2' ..etc
CALIBRATED_MS = 'src' #final calibrated ms for imaging
MIN_SNR = 2.0 #minimum SNR for gaincal

#class Band:
  #band name, GHZ range, MHZ range, Angular res, Solint?

  
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
#note: configurations A=1,B=2,C=3,D=4
BAND_ANGULAR_RESOLUTION = {'4': [800,2200,20000,20000],
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



