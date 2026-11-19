#the prefix import.json stores archive paths under; the project root itself is found
#by marker file (classes/creds.project_root), so a renamed clone still works
FOLDER_NAME = 'hvla_image_machine'
#relative on purpose: they resolve against the work directory (classes/work_dir)
MS_SUB_PATH = 'measurement_sets/'
IMAGES_PATH = 'images/ '
IMPORT_JSON = 'import.json'
RS_IMPORT = 'radio_search_results.json'
DATA_ARCHIVE = 'data_archive/' #local dir for raw archives downloaded from Delos (per-project subdir)
#raw VLA archive file extensions accepted for import; an MS is a '.ms' directory,
#handled separately. A segment is often several of these, which importvla concatenates.
ARCHIVE_SUFFIXES = ('.exp', '.dat')
#Measurment set Name Defaults
FULLMS = 'fullset' # for the full MS before splitting
PRIMARY_CAL_MS = 'initial'

GAINCAL_G0ALL =  '.G0all'
BANDPASS_B0 = '.B0'
GAINCAL_G1 = '.G1'
FLUXSCALE_X = '.fluxscale' # + '1','2' ..etc
CALIBRATED_MS = 'source' #final calibrated ms for imaging

GAINCAL_G2 = '.G2'
SELF_CAL= '.selfcal'
BLCAL_P = '.blcal_p'   #per-baseline phase caltable (final blcal polish)
BLCAL_AP = '.blcal_ap' #per-baseline amp+phase caltable

#Defualts/ Thresholds
DEFAULT_IMAGE_SIZE = [1080,1080] # keep me a perfect Square!
INITIAL_NITER = 250 # half of niter from tutorial
MIN_SNR = 3.0 #a default min SNR for gaincal
FIRST_IMAGE = 'image'
MIN_FLUX_FOR_SELF_CAL = 0.02 #Jy/beam; skip self-cal below this peak (too faint to solve on)
#Baseline (blcal) calibration solves ~N^2/2 per-baseline terms, so it needs far more
#SNR than antenna-based self-cal and can absorb real structure -> higher peak floor.
MIN_FLUX_FOR_BASELINE_CAL = 0.1 #Jy/beam; opt-in blcal only runs on bright sources above this
#--- imaging (tclean) ---
#Shared by every clean in a run; cycles are scored against each other by dynamic range,
#so they must match. Applied in Cleaner._tclean_kwargs.
CLEAN_ROBUST = 0.5             #briggs robust
CLEAN_SMALL_SCALE_BIAS = 0.7   #multiscale small-scale bias
CLEAN_NTERMS = 1               #jvla = 2, HVLA = 1
CLEAN_NITER = 9999             #safety cap; SELF_CAL_NSIGMA is the real stop
#negative = no T/F blanking, |value| is still the cutoff; small so the corner RMS
#boxes hold noise, not un-normalized zeros
CLEAN_PBLIMIT = -0.01
SELF_CAL_INITIAL_NITER = 1000  #initial clean is shallow: it only feeds the first gaincal
#--- core subtraction ---
#Clean only the compact core into the model, uvsub it out, then image what is left
#(the jet). 'auto' masks a circle this many synthesized beams around the fitted peak;
#'manual' has the user draw the core mask, as 1.99 did.
CORE_MASK_BEAMS = 2
#Below this peak the auto mask is likely sitting on noise rather than a core, so the
#subtraction is warned about (not skipped -- it is a product the user asked for).
MIN_FLUX_FOR_CORE_SUBTRACT = 0.02 #Jy/beam
CORE_SUBTRACT_SUFFIX = '_coresub'  #image name; the subtracted MS is <calibrated>_sub.ms
#--- test image ---
#A quick, shallow clean shown before the real imaging so cell/image size/robust can be
#judged on this data rather than guessed. Cheap on purpose: it is thrown away.
TEST_IMAGE_NITER = 200
TEST_IMAGE_SUFFIX = '_test'
#--- self-calibration during imaging ---
#Phase-only solint schedule. Normally built per-observation by
#Cleaner._build_solint_schedule ('inf' -> geometric halving from ~half a scan down to
#the integration time -> 'int'); this fixed ladder is the FALLBACK when the scan /
#integration times can't be read from the MS. Padded with 'int' if more cycles are asked.
SELF_CAL_SOLINTS = ['inf', '60s', '30s', 'int']
SELF_CAL_SOLINT_FACTOR = 2  #solint shortening ratio per cycle (2 = halve each step)
SELF_CAL_DEFAULT_CYCLES = 4 #enough for the full inf -> 60s -> 30s -> int ladder
SELF_CAL_FINAL_AP = True            #run one calmode='ap' pass after the phase cycles converge
SELF_CAL_NSIGMA = 3.0               #tclean stop threshold (both modes); replaces a blind niter
#Phase-cycle clean depth, keyed on the cycle's solint not its index, so a user-chosen
#solint gets the matching depth: long solint = poorer model -> clean shallower.
SELF_CAL_NSIGMA_INF = 5.0           #solint='inf'
SELF_CAL_NSIGMA_LONG = 4.0          #solint longer than SELF_CAL_LONG_SOLINT_S
SELF_CAL_LONG_SOLINT_S = 60         #seconds; above this a solint counts as long
SELF_CAL_MIN_IMPROVEMENT_PCT = 10   #stop self-cal once an improving cycle gains < this % in dynamic range
SELF_CAL_AP_MAX_FLUX_LOSS_PCT = 5   #reject the a&p pass if integrated flux drops more than this %
SELF_CAL_MAX_GUIDED_CYCLES = 12     #hard cap on 'guided', where the user, not the schedule, ends the loop
#--- data flagging ---
#Methods the flagging decision can run, one flagdata pass each. Insertion order IS
#the run order: the deterministic passes must precede tfcrop, whose statistics are
#skewed by zeros and scan-start settling, and extend grows what the autoflagger found.
FLAG_CLIPZEROS = 'clipzeros'
FLAG_QUACK     = 'quack'
FLAG_SHADOW    = 'shadow'
FLAG_AUTOCORR  = 'autocorr'
FLAG_TFCROP    = 'tfcrop'
FLAG_EXTEND    = 'extend'
FLAG_RFLAG     = 'rflag'
FLAG_METHODS = {m: m for m in (FLAG_CLIPZEROS, FLAG_QUACK, FLAG_SHADOW, FLAG_AUTOCORR,
                               FLAG_TFCROP, FLAG_EXTEND, FLAG_RFLAG)}
FLAG_METHODS_DEFAULT = (FLAG_TFCROP,)
FLAG_QUACK_INTERVAL = 5.0     #seconds dropped at each scan start (settling)
FLAG_EXTEND_GROWTIME = 60.0   #% of a baseline's timerange flagged -> flag the rest of it
FLAG_RFLAG_TIMEDEVSCALE = 5.0
#every spw in this data is 1 channel, so tfcrop/rflag fit in time only and
#edge-channel flagging does not apply
#--- gaincal solution failure rate (flagged fraction of a caltable) ---
GAINCAL_APPLYMODE_CUTOFF_PCT = 5    #primary applycal: > this failure rate -> 'calonly' (don't flag), else 'calflag'
GAINCAL_WARN_PCT = 10               #warn (solint likely too short / SNR too low / bad refant) above this failure rate
#--- image measurement (classes/image_data.py) ---
#Where the off-source noise is measured. False: the user designates one region, asked
#once and reused for every image in the run. True: the automatic four-corner median
#below. The automatic path is also the fallback whenever no region can be obtained
#(an imported replay, a piped run), so an unattended run always scores.
DO_MEAN_RMS = False
#Automatic path: the RMS is measured in four corner boxes and the median taken, so one
#corner holding a sidelobe or a field source can't drag the estimate. Boxes are inset
#from the very edge, where gridding artifacts live.
RMS_CORNER_BOX_FRACTION = 0.25      #corner box side, as a fraction of the shorter image side
RMS_EDGE_MARGIN_FRACTION = 0.02     #inset from the image edge, same units
MAD_TO_SIGMA = 1.4826               #robust fallback estimator: sigma = 1.4826 * MAD
#--- 2D Gaussian source fit (image_generation/source_fit.py) ---
FIT_BOX_BEAMS = 10                  #imfit box half-side, in synthesized beams, around the peak
FIT_BOX_MIN_PIXELS = 32             #...but never smaller than this
FIT_BOX_MAX_IMAGE_FRACTION = 0.25   #...and never more than this fraction of the shorter image
                                    #side, so an over-sampled image (many pixels per beam)
                                    #can't grow the box back to the whole frame
#--- measuring the target where the catalogue puts it ---
#The target is measured at its NED position, not wherever the image happens to peak:
#otherwise a brighter field source, a sidelobe or a noise streak is fitted and
#reported as the target. Below the threshold the result is an upper limit.
DETECTION_SIGMA = 5.0               #default detection threshold, in off-source rms;
                                    #options.detection_sigma (import.json) overrides it
DETECTION_SEARCH_BEAMS = 1.0        #the target's peak is looked for within this many beams
                                    #(major axis) of its catalogue position
FIT_TARGET_BOX_BEAMS = 3            #imfit box half-side, in beams, around the target
FIT_MIN_SNR = 3.0                   #below this S/N no Gaussian is fitted at all (it would fit
                                    #noise); kept below DETECTION_SIGMA so a sweep can be
                                    #re-thresholded down to it without re-imaging
PB_FWHM_ARCMIN_GHZ = 45.0           #classic VLA 25 m primary beam FWHM ~ 45'/freq(GHz)...
PB_FWHM_ARCMIN_GHZ_BAND = {'P': 49.0}  #...but P band's prime-focus dipoles see wider: 150' at
                                    #327 MHz (VLA status summary)
CASA_PB_FWHM_ARCMIN_GHZ = 43.0      #CASA's own VLA model (tclean's pb, hence pbcor) is one shape
                                    #scaled by frequency, zero past 1.19 FWHM: at P band 131' FWHM,
                                    #zero past 156' (measured on AD0308, 327.5 MHz), narrower than 150'
#--- field of view (Cleaner.plan_field) ---
#Every source in the primary beam that is bright enough to matter has to be in the
#self-cal model, at the right place: a faint target can sit under the sidelobes of a
#field source a thousand times brighter, whatever the exposure. That does not need one
#huge image: a modest image centred on the pointing models the inner field, and every
#catalogued source beyond it that is bright enough after the primary beam gets a small
#outlier field of its own, cleaned jointly with it (as AIPS SETFC/IMAGR facets do).
#A wide, tapered image of the residuals then catches what the catalogue missed.
FIELD_OF_VIEW_PRIMARY_BEAM = 'primary_beam' #main image + outlier fields over the beam
FIELD_OF_VIEW_FIXED = 'fixed'       #image_size and cell as given (fast mode)
MAIN_IMAGE_PIXELS = 1024            #main image side, pixels...
MAIN_IMAGE_PIXELS_BAND = {'P': 4096}  #...wider where 1024 cannot hold the beam: at P band it is
                                    #19' (A), 63' (B), 205' (C) against a 150' beam
MAIN_CELLS_PER_BEAM = 5             #...at this many pixels per synthesized beam
FOV_PB_FWHMS = 2.0                  #never wider than this many primary-beam FWHMs (D config)
CELLS_PER_BEAM = 10                 #fixed (fast) mode's default sampling of the beam
WPROJECT_THRESHOLD = 0.3            #w-projection when (half-width, rad)^2 * Bmax/lambda exceeds this
OUTLIER_SEARCH_FWHMS = 2.0          #catalogue (NVSS) sources this far out are considered
OUTLIER_MIN_APPARENT_JY = 0.005     #...and kept when their beam-attenuated flux reaches this
OUTLIER_SPECTRAL_INDEX = -0.7       #to carry NVSS 1.4 GHz fluxes to the observing frequency
PB_SIDELOBE_FLOOR = 0.02            #response floor out to OUTLIER_SEARCH_FWHMS: the Gaussian beam
                                    #underestimates the skirt (an L-band source 1.3 FWHM out
                                    #measured 1.6%, the Gaussian says 0.8%)
OUTLIER_MAX_FWHMS = 1.0            #no outlier field further out: CASA's VLA beam model is zero
                                    #beyond ~1.1 FWHM and tclean then cannot clean the field
                                    #("No valid values to deconvolve"); such sources are warned of
OUTLIER_MAX_FWHMS_BAND = {'P': 0.85}  #P band: CASA's narrower model (131') is below the 1% pblimit
                                    #past 137', so 1.0 x 150' would already be outside it
OUTLIER_FIELD_BEAMS = 40            #outlier field side, in synthesized beams (at least 64 pixels)
MAX_OUTLIER_FIELDS = 20
MAX_IMAGING_CHANNELS = 16           #spectral-line data is averaged to at most this many channels
                                    #per spectral window before imaging (as continuum)
OUTLIER_MASK_BEAMS = 5              #mask radius, in beams, for an outlier field with no mask of
                                    #its own in a clean on saved masks
#--- residual sweep (Cleaner.residual_sweep) ---
#The catalogue misses some bright sources: flat-spectrum ones at high frequency, ones
#that have flared since NVSS, and the sky south of -40 deg. Any of them left out of the
#model sprays its sidelobes over the main image. A dirty image of the residual
#visibilities (data - model), tapered to low resolution so it covers a wide field in
#few pixels, shows such a source as a peak at its true position.
SWEEP_PB_FWHMS = 3.0                #residual image side, in primary-beam FWHMs
SWEEP_BEAMS_PER_FWHM = 40           #taper to a beam of FWHM / this (no finer than the array's)
SWEEP_CELLS_PER_BEAM = 4
SWEEP_SIGMA = 6.0                   #a residual peak this many sigma outside every field...
SWEEP_SIDELOBE_FRACTION = 0.2       #...and at least this fraction of the brightest residual
                                    #inside the fields (else it may be that field's sidelobe)
SWEEP_MAX_SOURCES = 5               #outlier fields added per sweep
SWEEP_BLANK_BEAMS = 3               #radius blanked around each found peak before the next
#--- automatic clean masks (auto-multithresh) ---
#CASA's defaults are tuned for ALMA. A classic-VLA snapshot's PSF has sidelobes of
#~0.4, so the default 3x-sidelobe threshold masks nothing, and what the 2x VLA value
#leaves above it is smaller than the default 0.3-beam pruning size: nothing is cleaned
#and the field's sidelobes stay in the image (an L-band snapshot measured 5x noisier).
#The CASA automasking guide's VLA values, with pruning lowered to keep the first peaks.
AUTOMASK_VLA = {'sidelobethreshold': 2.0, 'noisethreshold': 4.25, 'lownoisethreshold': 1.5,
                'minbeamfrac': 0.1, 'negativethreshold': 0.0}
AUTOMASK_NOISE_A_CONFIG = 5.0       #noisethreshold the guide gives for A configuration
#--- self-calibration gate ---
#Judged on the whole field: the model of everything cleaned is what gaincal solves against.
MIN_MODEL_FLUX_FOR_SELF_CAL = 0.02  #Jy summed over the field model; below, too faint to solve on
#--- warnings: epochs where a faint target will be hard ---
LOW_FREQUENCY_BANDS = ('4', 'P', 'L', 'S', 'C')  #big primary beams, many bright field sources
LOW_PB_WARN = 0.5                   #target this far down the beam at a low frequency
PB_RELIABLE_FWHMS = 0.75            #beyond this CASA's VLA beam model drops well below what is
                                    #measured (0.8 FWHM: 0.10 vs Gaussian 0.17; zero past 1.1,
                                    #where a source was seen at 1.6%): the correction is uncertain
PB_RELIABLE_FWHMS_BAND = {'P': 0.4}  #P band: CASA's 131' model and the 150' beam differ by more
                                    #than 10% beyond 0.4 FWHM (60'), by 2x at 0.7 FWHM
DR_WARN_RATIO = 1000                #a catalogued field source this many times the image rms
#--- image quality ---
#Stokes V is effectively source-free here, so Stokes I noise well above V's is structure
#left in I: the image is limited by dynamic range or calibration, not by noise. V is
#not the thermal noise itself -- bad data and short snapshots raise both together.
NOISE_RATIO_WARN = 2.0              #flag an image whose I/V noise ratio is above this
STOKES_V_MAX_PIXELS = 1024          #the V image is a central cutout: only its noise is used

#class Band:
  #band name, GHZ range, MHZ range, Angular res, Solint?
#calibration source type 
TYPE_FLUX_CAL = 'flux_calibrator'
TYPE_PHASE_CAL = 'phase_cal'
TYPE_TARGET = 'target'
AUTO = 'auto'
SELF_PHASE_CAL = False

#Constants that may be integrated, but are being placed here for reference!
BAND_GHZ_RANGES = {'P': [0.200, 0.500],
                   'L': [0.985, 2.025],
                   'S': [2.026, 4.013],
                   'C': [4.309, 7.461], 
                   'X': [8.000, 11.512], 
                   'Ku': [13.133, 18.000], 
                   'K': [20.000, 26.412], 
                   'Ka': [28.258, 37.011], 
                   'Q': [43.148, 48.873]}
BAND_MHZ_RANGES = {'P': [200.0, 500.0],
                   'L': [985.0, 2025.0],
                   'S': [2026.0, 4013.0],
                   'C': [4309.0, 7461.0], 
                   'X': [8000.0, 11512.0], 
                   'Ku': [13133.0, 18000.0], 
                   'K': [20000.0, 26412.0], 
                   'Ka': [28258.0, 37011.0], 
                   'Q': [43148.0, 48873.0],}
#Bands run only with a person at them. Classic-VLA P band (90 cm) is new here and unvetted:
#ionosphere, RFI, and a primary beam CASA models poorly. A run in one stops unless someone
#is at the display and the terminal, and then cleans interactively and reviews the flags
#(decisions.require_attended). The 4 band (74 MHz) is not supported at all.
EXPERIMENTAL_BANDS = ('P',)
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
                           'C': [8.9,29,240,240],
                           'X': [5.3,17,145,145],
                           'Ku':[3.6,12,97,97],
                           'K': [2.4,7.9,66,66],
                           'Ka':[1.6,5.3,44,44],
                           'Q': [1.2,3.9,32,32]
}
ARRAY_CONFIGURATION = 1
#Multiscale clean scale ladder, as multiples of the synthesized beam (converted to
#pixels at imaging time). A 0 (point-source) term plus a short ladder. The largest
#scale is additionally capped by the band/config LAS (BAND_LARGEST_SCALE) -- cleaning
#structure larger than the array's Largest Angular Scale just fits noise -- and by the
#image size. Only used by scale-sensitive deconvolvers (multiscale/mtmfs).
MULTISCALE_BEAM_MULTIPLIERS = [0, 2, 5]

BAND_SOLINT = {'4':'900', 'P':'900', 'L':'450', 'S':'450', 'C':'240', 'X':'240', 'Ku':'180', 'U':'180', 'K':'120', 'Ka':'90', 'Q':'60'}

#VLA listobs names: B1950 (older data) and J2000, short and long forms
FLUX_CAL_ALIASES = {'1331+305': '3C286',
                      '1328+307': '3C286',
                      '1331+3030': '3C286',
                      '0542+4951': '3C147',
                      '0542+498': '3C147',
                      '0538+498': '3C147',
                      '0137+3309': '3C48',
                      '0134+329': '3C48',
                      '0137+331': '3C48',
                      '0521+1638': '3C138',
                      '0521+166': '3C138',
                      '0518+165': '3C138'} #upgrade with calibrator list, and pull flux data for 'custom' callibrators
#variable (3C138 flares): auto takes these only when no other flux calibrator is observed
FLUX_CAL_LAST_RESORT = ('3C138',)
#setjy's flux-density standard. Perley-Butler 2013 is fitted over 1-50 GHz; 2017 extends to
#50 MHz, so it is the one for P band. The other bands keep 2013, so earlier results don't shift.
FLUX_STANDARD = 'Perley-Butler 2013'
FLUX_STANDARD_BAND = {'P': 'Perley-Butler 2017'}


#--- archive search results ---
#radio_search returns both old-style VLA and JVLA-era observations, but the download
#path only understands old-style archive segments: a JVLA project's --archfileinfo
#lists scheduling blocks, parses to zero segments, and dies at importvla with nothing
#to import. Observations from this year on are the JVLA-era ones (so "historical"
#means 2008 and earlier); they are shown in red, and hidden outright when
#RADIO_SEARCH_HISTORICAL_ONLY is set.
RADIO_SEARCH_MODERN_YEAR = 2009
RADIO_SEARCH_HISTORICAL_ONLY = True   #False shows JVLA-era rows again, marked red

#--- decision points (Breakpoints 2.0) ---
#Every point where the pipeline picks something the user may want to see or override.
#Modes are uniform: off = skip the stage, auto = decide silently, verify = decide then
#show and let the user accept/override, manual = the user supplies the value.
#force (phase cal) and guided (self-cal) are the two point-specific modes.
OFF, VERIFY, MANUAL = 'off', 'verify', 'manual'
FORCE, GUIDED = 'force', 'guided'

#'gui' groups the dropdown into the GUI's calibration or image frame. 'methods' is an
#optional multi-select rendered beside the mode dropdown; the mode itself is still one string.
DECISIONS = {
  'flux_cal':     {'label': 'Flux calibrator',      'modes': (AUTO, VERIFY, MANUAL), 'default': AUTO, 'gui': 'calibration'},
  'phase_cal':    {'label': 'Phase calibrator',     'modes': (AUTO, FORCE, MANUAL),  'default': AUTO, 'gui': 'calibration'},
  'refant':       {'label': 'Reference antenna',    'modes': (AUTO, MANUAL),         'default': AUTO, 'gui': 'calibration'},
  'flagging':     {'label': 'Data flagging',        'modes': (OFF, AUTO, VERIFY, MANUAL), 'default': AUTO, 'gui': 'calibration',
                   'methods': FLAG_METHODS, 'methods_default': FLAG_METHODS_DEFAULT},
  'self_cal':     {'label': 'Self-calibration',     'modes': (OFF, AUTO, GUIDED),    'default': OFF,  'gui': 'image'},
  'baseline_cal': {'label': 'Baseline cal (blcal)', 'modes': (OFF, AUTO, VERIFY),    'default': OFF,  'gui': 'image'},
  'core_subtract':{'label': 'Core subtraction',     'modes': (OFF, AUTO, MANUAL),    'default': OFF,  'gui': 'image'},
}



