from __future__ import annotations

from classes.constants import *
import casatasks as ct
from pre_calibration import options_class
from classes import *
import pprint as pp
from data_calibration import parse_listobs as parse

from pathlib import Path
# MS_SUB_PATH +
def self_phase_cal(options:options_class.Options):
  '''perform self cal on phase calibrator'''#do normal cal just without a phase cal field
  find_refant(options) #do again incase it's starting with a calibrated dataSet
  fields = str(options.amp_cal.initial_ms_fieldID)+","+str(options.source_ids.initial_ms_fieldID)
  if not Path(options.initial_calibration_filename + GAINCAL_G0ALL).is_dir():
    gaincal_out1 =ct.gaincal(vis=options.initial_calibration_filename+'.ms',
                                caltable=options.initial_calibration_filename+GAINCAL_G0ALL,
                                field=fields, 
                                spw='',      #leave blank for all spws option
                                solint='int', 
                                refant=options.ref_ant,
                                calmode='p',
                                gaintype='G',
                                minsnr=options.min_snr,
                                append=False,
                                parang=False)
    #flag for data flagging here
    #.G0? -> G0All technically G0 with no flagging(?)
  if not Path(options.initial_calibration_filename+BANDPASS_B0).is_dir():
    bandpass_output = ct.bandpass(vis=options.initial_calibration_filename+'.ms',
                                  caltable=options.initial_calibration_filename+BANDPASS_B0,
                                  field=options.amp_cal.listobs_name,
                                  spw='',
                                  refant=options.ref_ant,
                                  solint='inf',
                                  bandtype='B',
                                  combine='scan',
                                  gaintable=[options.initial_calibration_filename+GAINCAL_G0ALL],
    )
 
  if not Path(options.initial_calibration_filename+GAINCAL_G1).is_dir():
    #apply bandpass cal to flux model and source
    gaincal_output2 = ct.gaincal(vis=options.initial_calibration_filename+'.ms',
                               caltable=options.initial_calibration_filename+GAINCAL_G1,
                               field=options.amp_cal.listobs_name,
                               spw='', 
                               solint='inf',
                               refant=options.ref_ant,
                               gaintype='G',
                               calmode='ap',
                               solnorm=False,
                               gaintable=[options.initial_calibration_filename+BANDPASS_B0],
                               interp=['nearest']
     )
    #apply to source
    gaincal_out3 = ct.gaincal(vis=options.initial_calibration_filename+'.ms',
                            caltable=options.initial_calibration_filename+GAINCAL_G1,
                            field=options.source_ids.listobs_name,
                            spw='',
                            solint='inf',
                            refant=options.ref_ant,
                            gaintype='G',
                            calmode='ap',
                            solnorm=False,
                            gaintable=[options.initial_calibration_filename+BANDPASS_B0],
                            append=True
    )
  if not Path(options.initial_calibration_filename+FLUXSCALE_X+'1').is_dir():
    #transfer flux from amp_cal to phase_cal
    fluxScale_out = ct.fluxscale(vis=options.initial_calibration_filename+'.ms',
                            caltable=options.initial_calibration_filename+GAINCAL_G1,
                            fluxtable=options.initial_calibration_filename+FLUXSCALE_X + '1',
                            reference=[options.amp_cal.listobs_name], #fluxdensity model calibrator
                            transfer=[options.source_ids.listobs_name], #nodder,
                            incremental=False
    )
  if not Path(options.calibrated_filename+'.ms').is_dir():
    #adaptive applymode from the G1 gaincal failure rate (see amp_phase_cal)
    apply_mode = choose_applymode(options.initial_calibration_filename + GAINCAL_G1)
    apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
           field= options.amp_cal.listobs_name ,
           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
           gainfield=[options.amp_cal.listobs_name,''],
           interp=['nearest',''], #['nearest','linear']?
           calwt=[False], #true?
           applymode=apply_mode,
    )
    apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
           field=options.source_ids.listobs_name,
           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
           gainfield=[options.source_ids.listobs_name,''],
           interp=['linear',''], #['nearest','linear']?
           calwt=[False], #true?
           applymode=apply_mode,
    )


def amp_phase_cal(options:options_class.Options):
  """
  Performs initial calibration on flux, phase calibrator, and source 
  """
  find_refant(options)
  if not Path(options.initial_calibration_filename + GAINCAL_G0ALL).is_dir():
    #define fields in init.ms
    fields = str(options.amp_cal.initial_ms_fieldID)+","+str(options.source_ids.initial_ms_fieldID) + ',' + str(options.phase_cal.initial_ms_fieldID)
    #initial phase calibration
    gaincal_output = ct.gaincal(vis=options.initial_calibration_filename+'.ms',
                                caltable=options.initial_calibration_filename+GAINCAL_G0ALL,
                                field=fields, 
                                spw='',      #leave blank for all spws option
                                solint='int', 
                                refant=options.ref_ant,
                                calmode='p',
                                gaintype='G',
                                minsnr=options.min_snr,
                                append=False,
                                parang=False)
    
  #bandpass cal
  if not Path(options.initial_calibration_filename+BANDPASS_B0).is_dir():
    bandpass_output = ct.bandpass(vis=options.initial_calibration_filename+'.ms',
                                  caltable=options.initial_calibration_filename+BANDPASS_B0,
                                  field=options.amp_cal.listobs_name,
                                  spw='',
                                  refant=options.ref_ant,
                                  solint='inf',
                                  bandtype='B',
                                  combine='scan',
                                  gaintable=[options.initial_calibration_filename+GAINCAL_G0ALL],
    )
  #possible flagging_breakpoint here
  #2nd gain cal passes
  if not Path(options.initial_calibration_filename+GAINCAL_G1).is_dir():
    #apply AP cal to flux model
    gaincal_output2 = ct.gaincal(vis=options.initial_calibration_filename+'.ms',
                               caltable=options.initial_calibration_filename+GAINCAL_G1,
                               field=options.amp_cal.listobs_name,
                               spw='', 
                               solint='inf',
                               refant=options.ref_ant,
                               gaintype='G',
                               calmode='ap',
                               solnorm=False,
                               gaintable=[options.initial_calibration_filename+BANDPASS_B0],
                               interp=['nearest']
     )
    #apply to source
    gaincal_out3 = ct.gaincal(vis=options.initial_calibration_filename+'.ms',
                            caltable=options.initial_calibration_filename+GAINCAL_G1,
                            field=options.phase_cal.listobs_name,
                            spw='',
                            solint='inf',
                            refant=options.ref_ant,
                            gaintype='G',
                            calmode='ap',
                            solnorm=False,
                            gaintable=[options.initial_calibration_filename+BANDPASS_B0],
                            append=True
   )
  if not Path(options.initial_calibration_filename+FLUXSCALE_X+'1').is_dir():
    #transfer flux from amp_cal to phase_cal
    fluxScale_out = ct.fluxscale(vis=options.initial_calibration_filename+'.ms',
                            caltable=options.initial_calibration_filename+GAINCAL_G1,
                            fluxtable=options.initial_calibration_filename+FLUXSCALE_X + '1',
                            reference=[options.amp_cal.listobs_name], #fluxdensity model calibrator
                            transfer=[options.phase_cal.listobs_name], #nodder,
                            incremental=False
   )
  
  if not Path(options.calibrated_filename+'.ms').is_dir():
    print(f"applying calibrations to {options.initial_calibration_filename+'.ms'}'s name : {options.source_ids.listobs_name} field ID: {options.source_ids.initial_ms_fieldID}")
    #adaptive applymode: measure the gaincal failure rate (flagged fraction of G1, the
    #gains that feed fluxscale) and flag the un-solved data only if few solutions failed;
    #otherwise apply where solved without flagging, so a poor solve can't gut the dataset.
    apply_mode = choose_applymode(options.initial_calibration_filename + GAINCAL_G1)
    apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
           field= options.amp_cal.listobs_name ,
           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
           gainfield=[options.amp_cal.listobs_name,''],
           interp=['nearest',''], #['nearest','linear']?
           calwt=[False], #true?
           applymode=apply_mode,
    )
    apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
           field= options.phase_cal.listobs_name ,
           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
           gainfield=[options.phase_cal.listobs_name,''],
           interp=['nearest',''], #['nearest','linear']?
           calwt=[False], #true?
           applymode=apply_mode,
    )
    apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
           field=options.source_ids.listobs_name,
           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
           gainfield=[options.phase_cal.listobs_name,''],
           interp=['linear',''], #['nearest','linear']?
           calwt=[False], #true?
           applymode=apply_mode,
    )

  #return to data_data_cal and split of callibrated data

def baseline_cal(options:options_class.Options):
  '''Final baseline-based (blcal) calibration on the self-calibrated source MS.

  Solves a per-baseline phase term, then a per-baseline amp+phase term (using the
  phase solution as prior), and applies both. This mops up *non-closing* errors
  (baseline/correlator artifacts) that antenna-based gaincal mathematically cannot
  represent. solint='inf' -> one solution per baseline over the whole observation,
  the highest-SNR (safest) choice for this final polish.

  blcal has ~N^2/2 free parameters, so it can absorb real source structure on a
  faint/extended target; the caller gates this on a bright source and keeps the
  result only if it improves the image. applymode='calonly' so a poor solve gaps
  rather than flags the data.
  '''
  vis = options.calibrated_filename + '.ms'
  p_table = options.calibrated_filename + BLCAL_P
  ap_table = options.calibrated_filename + BLCAL_AP
  #fresh tables each run (blcal fails on a pre-existing caltable)
  for tbl in (p_table, ap_table):
    if Path(tbl).is_dir():
      ct.rmtables(tbl)
  ct.blcal(vis=vis, caltable=p_table, calmode='p', solint='inf')
  ct.blcal(vis=vis, caltable=ap_table, calmode='ap', solint='inf', gaintable=[p_table])
  ct.applycal(vis=vis, gaintable=[ap_table, p_table],
              calwt=[False], applymode='calonly')

def self_cal_cycle(options:options_class.Options,cycle_number,solint='inf',calmode='p'):
  '''
  Perform one cycle of self calibration.

  solint : gaincal solution interval. The self-cal loop shortens this each cycle
           (e.g. inf -> 60s -> 30s -> int) as the model/SNR improves.
  calmode: 'p' for the phase-only cycles, 'ap' for a final amplitude+phase pass.
           Amplitude solutions are normalised (solnorm=True) so self-cal corrects
           the gain shape without rescaling the source's absolute flux.

  Solutions below options.min_snr are dropped, and applycal runs 'calonly' (gap,
  don't flag, the failed solutions) so repeated cycles can't silently eat data.
  '''
  find_refant(options) #do again incase it's starting with a calibrated dataSet
  cycle_number = str(cycle_number)
  caltable = options.calibrated_filename+SELF_CAL+cycle_number
  ct.gaincal(vis=options.calibrated_filename+'.ms',
             caltable=caltable,
             field='',
             spw='',
             selectdata=False,
             solint=solint,
             refant=options.ref_ant,
             gaintype='G',
             calmode=calmode,
             minsnr=options.min_snr,
             solnorm=(calmode=='ap')
             )
  #diagnostic only: report how many self-cal solutions failed (high -> solint likely
  #too short for the current SNR). applymode stays 'calonly' regardless, by design.
  rate = gaincal_failure_rate(caltable)
  if rate is not None:
    warn = "  <-- high; consider a longer solint" if rate*100 > GAINCAL_WARN_PCT else ""
    print(f"  self-cal solint={solint} calmode={calmode}: gaincal failure rate {rate*100:.1f}%{warn}")
  ct.applycal(vis=options.calibrated_filename+'.ms',
              field='',spw='',
              selectdata=False,
              gaintable=[caltable],
              gainfield=[''],
              interp=['nearest'],
              calwt=[False],applymode='calonly') #gap (don't flag) failed/low-SNR solutions

def self_cal_solint_variation(options:options_class.Options,cycle_number,solint):
  '''
  Perform one cycle of self calibration with 
  '''
  find_refant(options) #do again inc
  cycle_number = str(cycle_number)
  ct.gaincal(vis=options.calibrated_filename+'.ms',
             caltable=options.calibrated_filename+SELF_CAL+cycle_number,
             field='',
             spw='',
             selectdata=False,
             solint=solint,
             refant=options.ref_ant,
             gaintype='G',
             calmode='p'
             )
  ct.applycal(vis=options.calibrated_filename+'.ms',
              field='',spw='',
              selectdata=False,
              gaintable=[options.calibrated_filename+SELF_CAL+cycle_number],
              gainfield=[''],
              interp=['nearest'],
              calwt=[False],applymode='calflag') #calflag vs. calonly
  
def find_refant(options:options_class.Options):
  """
  Identify the reference antenna for calibration
  """
  if options.ref_ant is None:
    anntennas_list = parse.antennas_distance(options) #sorted list of antennas by distance 
    options.ref_ant = anntennas_list[3]['id'] #closest antenna by name ie "VA01" #3rd closest by vibes

def check_refant(options,gaincal_out):
  """
  Check which reference antenna was used in gaincal, for future gaincal calls
  """
  pass

def gaincal_failure_rate(caltable):
  """Fraction of gaincal solutions that failed, read straight from the caltable.

  A gaincal solution (per antenna / interval / spw / pol) that fell below minsnr or
  did not converge is flagged in the caltable, so the flagged fraction of the FLAG
  column IS the failure rate -- no CASA-log scraping needed. Returns a float in
  [0, 1], or None if the table can't be read / has no solutions.
  """
  from pathlib import Path as _Path
  if not _Path(caltable).is_dir():
    return None
  import casatools
  tb = casatools.table()
  try:
    tb.open(caltable)
    flag = tb.getcol('FLAG')   #shape (npol, nchan, nsolutions)
  except Exception as exc:
    print(f"gaincal_failure_rate: could not read {caltable}: {exc}")
    return None
  finally:
    tb.close()
  total = flag.size
  if total == 0:
    return None
  return float(flag.sum()) / total

def choose_applymode(caltable):
  """Pick applycal's applymode from a caltable's gaincal failure rate, and warn when
  it's high (a symptom of too-short solint / low SNR / bad refant).

  Low failure  -> 'calflag' (apply gains, flag the little data that had no solution).
  High failure -> 'calonly' (apply where solved, DON'T flag the rest, or we'd gut the
                  dataset). Cutoff = GAINCAL_APPLYMODE_CUTOFF_PCT. Unknown -> 'calflag'
                  (CASA default), noted.
  """
  rate = gaincal_failure_rate(caltable)
  if rate is None:
    print(f"gaincal failure rate unknown for {caltable}; using applymode='calflag' (default).")
    return 'calflag'
  pct = rate * 100
  mode = 'calonly' if pct > GAINCAL_APPLYMODE_CUTOFF_PCT else 'calflag'
  note = "  <-- high: solint may be too short / SNR too low / refant poor" if pct > GAINCAL_WARN_PCT else ""
  print(f"gaincal failure rate {pct:.1f}% ({Path(caltable).name}) -> applymode='{mode}'{note}")
  return mode

def phase_self_calibration(options:options_class.Options):
  '''perform self cal on phase calibrator'''#do normal cal just without a phase cal field
  pass

#def amp_phase_cal(options:options_class.Options):
#  """
#  Performs initial calibration on phase calibrator and source
#  """
#  find_refant(options)
#  if not Path(options.initial_calibration_filename + GAINCAL_G0ALL).is_dir():
#    #define fields in init.ms
#    if options.self_phase_cal:
#      fields = str(options.amp_cal.initial_ms_fieldID)+","+str(options.source_ids.initial_ms_fieldID)
#    else:
#      fields = str(options.amp_cal.initial_ms_fieldID)+","+str(options.source_ids.initial_ms_fieldID) + ',' + str(options.phase_cal.initial_ms_fieldID)
#    #initial phase calibration
#    gaincal_output = ct.gaincal(vis=options.initial_calibration_filename+'.ms',
#                                caltable=options.initial_calibration_filename+GAINCAL_G0ALL,
#                                field=fields, 
#                                spw='',      #leave blank for all spws option
#                                solint='int', 
#                                refant=options.ref_ant,
#                                calmode='p',
#                                gaintype='G',
#                                minsnr=options.min_snr,
#                                append=False,
#                                parang=False)
#    
#  #bandpass cal
#  if not Path(options.initial_calibration_filename+BANDPASS_B0).is_dir():
#    bandpass_output = ct.bandpass(vis=options.initial_calibration_filename+'.ms',
#                                  caltable=options.initial_calibration_filename+BANDPASS_B0,
#                                  field=str(options.amp_cal.initial_ms_fieldID),
#                                  spw='',
#                                  refant=options.ref_ant,
#                                  solint='inf',
#                                  bandtype='B',
#                                  combine='scan',
#                                  gaintable=[options.initial_calibration_filename+GAINCAL_G0ALL],
#    )
#  #possible flagging_breakpoint here
#  #2nd gain cal passes
#  if not Path(options.initial_calibration_filename+GAINCAL_G1).is_dir():
#    #apply AP cal to flux model
#    gaincal_output2 = ct.gaincal(vis=options.initial_calibration_filename+'.ms',
#                               caltable=options.initial_calibration_filename+GAINCAL_G1,
#                               field=str(options.amp_cal.initial_ms_fieldID),
#                               spw='', 
#                               solint='inf',
#                               refant=options.ref_ant,
#                               gaintype='G',
#                               calmode='ap',
#                               solnorm=False,
#                               gaintable=[options.initial_calibration_filename+BANDPASS_B0],
#                               interp=['nearest']
#     )
#    #apply to source or phase cal depending on self_phase_cal
#    if options.self_phase_cal:
#      gaincal_output2 = ct.gaincal(vis=options.initial_calibration_filename+'.ms',
#                               caltable=options.initial_calibration_filename+GAINCAL_G1,
#                               field= str(options.source_ids.initial_ms_fieldID),
#                               spw='', 
#                               solint='inf',
#                               refant=options.ref_ant,
#                               gaintype='G',
#                               calmode='ap',
#                               solnorm=False,
#                               gaintable=[options.initial_calibration_filename+BANDPASS_B0],
#                               interp=['nearest'],
#                               append=True
#     )
#    else:
#      gaincal_out3 = ct.gaincal(vis=options.initial_calibration_filename+'.ms',
#                              caltable=options.initial_calibration_filename+GAINCAL_G1,
#                              field=str(options.phase_cal.initial_ms_fieldID)+','+str(options.source_ids.initial_ms_fieldID),
#                              spw='',
#                              solint='inf',
#                              refant=options.ref_ant,
#                              gaintype='G',
#                              calmode='ap',
#                              solnorm=False,
#                              gaintable=[options.initial_calibration_filename+BANDPASS_B0],
#                              append=True
#     )
#  if not Path(options.initial_calibration_filename+FLUXSCALE_X+'1').is_dir():
#    if options.self_phase_cal:
#      fluxScale_out = ct.fluxscale(vis=options.initial_calibration_filename+'.ms',
#                              caltable=options.initial_calibration_filename+GAINCAL_G1,
#                              fluxtable=options.initial_calibration_filename+FLUXSCALE_X + '1',
#                              reference=[options.amp_cal.listobs_name],
#                              transfer=[options.source_ids.listobs_name],
#                              incremental=False
#      )
#      #transfer flux from amp_cal to phase_cal
#    else:
#        fluxScale_out = ct.fluxscale(vis=options.initial_calibration_filename+'.ms',
#                              caltable=options.initial_calibration_filename+GAINCAL_G1,
#                              fluxtable=options.initial_calibration_filename+FLUXSCALE_X + '1',
#                              reference=[options.amp_cal.listobs_name],
#                              transfer=[options.phase_cal.listobs_name],
#                              incremental=False
#      )
#  
#  if not Path(CALIBRATED_MS+'ms').is_dir():
#    print(f"applying calibrations to {options.initial_calibration_filename+'.ms'}'s name : {options.source_ids.listobs_name} field ID: {options.source_ids.initial_ms_fieldID}")
#    apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
#           field = str(options.amp_cal.initial_ms_fieldID) ,
#           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
#           gainfield=[str(options.amp_cal.initial_ms_fieldID),''],
#           interp=['nearest',''],
#           calwt=[False],
#    )
#    if not options.self_phase_cal:
#      apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
#             field= str(options.phase_cal.initial_ms_fieldID) ,
#             gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
#             gainfield=[str(options.phase_cal.initial_ms_fieldID),''],
#             interp=['nearest',''],
#             calwt=[False],
#      )
#      apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
#             field=str(options.source_ids.initial_ms_fieldID),
#             gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
#             gainfield=[str(options.phase_cal.initial_ms_fieldID),''],
#             interp=['linear',''],
#             calwt=[False],
#      )
#    else:
#      apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
#             field=str(options.source_ids.initial_ms_fieldID),
#             gaintable=[options.initial_calibration_filename+GAINCAL_G1,options.initial_calibration_filename+BANDPASS_B0],
#             gainfield=[str(options.source_ids.initial_ms_fieldID),''],
#             interp=['linear',''],
#             calwt=[False],
#      )
#
  #return to data_data_cal and split of callibrated data