from __future__ import annotations

from classes.constants import *
import casatasks as ct
from pre_calibration import options_class
from classes import *
from classes import decisions, run_log
from classes.observations_class import vla_antenna_name
import pprint as pp
from data_calibration import parse_listobs as parse

import math
from statistics import median
from pathlib import Path
# MS_SUB_PATH +
def target_as_phase_cal(options:options_class.Options):
  '''perform self cal on phase calibrator'''#do normal cal just without a phase cal field
  find_refant(options) #do again incase it's starting with a calibrated dataSet
  fields = str(options.flux_cal.initial_ms_fieldID)+","+str(options.source_ids.initial_ms_fieldID)
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
                                  field=options.flux_cal.listobs_name,
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
                               field=options.flux_cal.listobs_name,
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
    fluxScale_out = ct.fluxscale(vis=options.initial_calibration_filename+'.ms',
                            caltable=options.initial_calibration_filename+GAINCAL_G1,
                            fluxtable=options.initial_calibration_filename+FLUXSCALE_X + '1',
                            reference=[options.flux_cal.listobs_name], #fluxdensity model calibrator
                            transfer=[options.source_ids.listobs_name], #nodder,
                            incremental=False
    )
  if not Path(options.calibrated_filename+'.ms').is_dir():
    #adaptive applymode from the G1 gaincal failure rate (see primary_calibration)
    apply_mode = choose_applymode(options.initial_calibration_filename + GAINCAL_G1)
    apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
           field= options.flux_cal.listobs_name ,
           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
           gainfield=[options.flux_cal.listobs_name,''],
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


def primary_calibration(options:options_class.Options):
  """
  Performs initial calibration on flux, phase calibrator, and source 
  """
  find_refant(options)
  if not Path(options.initial_calibration_filename + GAINCAL_G0ALL).is_dir():
    #define fields in init.ms
    fields = str(options.flux_cal.initial_ms_fieldID)+","+str(options.source_ids.initial_ms_fieldID) + ',' + str(options.phase_cal.initial_ms_fieldID)
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
                                  field=options.flux_cal.listobs_name,
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
                               field=options.flux_cal.listobs_name,
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
    #transfer flux from flux_cal to phase_cal
    fluxScale_out = ct.fluxscale(vis=options.initial_calibration_filename+'.ms',
                            caltable=options.initial_calibration_filename+GAINCAL_G1,
                            fluxtable=options.initial_calibration_filename+FLUXSCALE_X + '1',
                            reference=[options.flux_cal.listobs_name], #fluxdensity model calibrator
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
           field= options.flux_cal.listobs_name ,
           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
           gainfield=[options.flux_cal.listobs_name,''],
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

  Solves a per-baseline phase term, then amp+phase with that as prior, mopping up
  *non-closing* errors that antenna-based gaincal cannot represent. solint='inf'
  is the highest-SNR choice for a final polish.

  blcal has ~N^2/2 free parameters, so it can absorb real structure on a
  faint/extended target; the caller gates it on a bright source and keeps the
  result only if the image improves. applymode='calonly' so a poor solve gaps
  rather than flags.
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
  '''Perform one cycle of self calibration.

  solint : gaincal solution interval; the loop shortens it each cycle as the
           model/SNR improves.
  calmode: 'p' for the phase-only cycles, 'ap' for a final amp+phase pass.
           Amplitude solutions are normalised (solnorm=True) so the gain shape
           is corrected without rescaling the source's absolute flux.

  Solutions below options.min_snr are dropped, and applycal runs 'calonly' so
  repeated cycles can't silently eat data.
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
    run_log.event(f"self-cal cycle {cycle_number} (solint={solint}, calmode={calmode}): "
                  f"gaincal failure rate {rate*100:.1f}%{warn}")
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
  
#Refant scoring follows the ALMA/VLA pipeline's hif_refant heuristic:
#
#    S_i = (1 - d_i/max(d)) + (v_i/max(v))
#
#d_i is antenna i's distance from the array centre (the MEDIAN antenna position),
#v_i the number of UNFLAGGED visibilities involving it. Two terms, equally
#weighted. One count covers both ways a refant goes bad: heavily flagged and
#dropped-out-mid-track both leave fewer unflagged visibilities.
REFANT_LIST_SIZE = 4  #refant takes a prioritised list; 'flex' falls through it


def find_refant(options:options_class.Options, vis=''):
  """Pick the reference antenna once and keep it for the whole run.

  Every later gaincal/bandpass reuses options.ref_ant, so changing it between
  cycles would re-reference the phases mid-run. Returns the chosen name.
  """
  if options.ref_ant is not None:   #'' is a decision too: let CASA choose
    return options.ref_ant

  antennas = getattr(options.observation_data, 'antennas', None) or []
  names = [a.name for a in antennas]

  requested = str(getattr(options, 'reference_antenna', '') or '').strip()
  if requested and requested.lower() not in ('auto', 'default'):
    #accept either spelling -- a transition-era array is reported to the user as
    #VA##, so that is what they will type back -- but store the measurement set's
    #own name, which is what CASA resolves the selection against
    wanted = requested.lower()
    match = next((n for n in names
                  if wanted in (n.lower(), vla_antenna_name(n).lower())), '')
    if match:
      options.ref_ant = match
      run_log.event(f"Reference antenna {vla_antenna_name(match)} (requested)")
      return options.ref_ant
    shown = ', '.join(vla_antenna_name(n) for n in names[:6])
    print(f"find_refant: requested reference antenna {requested!r} is not in this "
          f"observation ({shown}...); choosing automatically.")

  options.ref_ant = _choose_refant(options, antennas, vis)
  if decisions.mode(options, 'refant') == MANUAL:
    options.ref_ant = _pick_refant(options, antennas, vis)
  return options.ref_ant


def _pick_refant(options:options_class.Options, antennas, vis=''):
  """Let the user choose from the scored ranking. Returns a refant string with the
  pick first, so the remaining alternates still cover a dropout."""
  ranked = _rank_antennas(options, antennas, vis)
  if not ranked:
    return options.ref_ant
  chosen = decisions.pick(
    'Reference antenna -- ranked by the hif_refant score:', ranked,
    formatter=lambda r: f"{vla_antenna_name(r[1]):<8} score {r[0]:.3f}")
  if not chosen:
    return options.ref_ant
  order = [chosen[1]] + [n for _, n in ranked if n != chosen[1]]
  decisions.announce('refant', vla_antenna_name(chosen[1]), 'picked')
  options.reference_antenna = vla_antenna_name(chosen[1])  #recorded for replay
  return ','.join(order[:REFANT_LIST_SIZE])


def _choose_refant(options:options_class.Options, antennas, vis=''):
  """Rank antennas by the hif_refant score; return a prioritised refant string.

  Falls back to ranking on distance alone when the MS cannot be read -- the same
  score with its flagging term disabled, which is what hif_refant's geometry-only
  mode does.
  """
  scored = _rank_antennas(options, antennas, vis)
  if not scored:
    print("find_refant: no antenna list; leaving refant unset for CASA to choose.")
    return ''

  ranked = [name for _, name in scored[:REFANT_LIST_SIZE]]
  #reported under VLA naming, returned as the measurement set spells it
  shown = [vla_antenna_name(name) for name in ranked]
  run_log.event(f"Reference antenna {shown[0]} (hif_refant score); "
                f"alternates {', '.join(shown[1:]) or 'none'}")
  return ','.join(ranked)


def _rank_antennas(options:options_class.Options, antennas, vis=''):
  """[(score, name), ...] best first, by the hif_refant score. Shared by the
  automatic choice and the manual picker."""
  if not antennas:
    return []
  distances = _centre_distances(antennas)
  furthest = max(distances.values()) or 1.0
  unflagged = _unflagged_visibilities(vis or _refant_vis(options), options)
  busiest = max(unflagged.values(), default=0.0) or 0.0

  scored = []
  for name, distance in distances.items():
    score = 1.0 - distance / furthest
    if busiest:
      score += unflagged.get(name, 0.0) / busiest
    scored.append((score, name))
  scored.sort(reverse=True)
  return scored


def _centre_distances(antennas):
  """{antenna name: metres from the array centre}.

  Centre is the MEDIAN antenna position, as hif_refant defines it -- a mean is
  dragged outward by one long arm of the Y.
  """
  east = median([a.east_offset for a in antennas])
  north = median([a.north_offset for a in antennas])
  return {a.name: math.hypot(a.east_offset - east, a.north_offset - north)
          for a in antennas}


def _refant_vis(options:options_class.Options):
  """The MS to measure antennas on -- whichever stage of the run we are at."""
  for attr in ('initial_calibration_filename', 'calibrated_filename', 'proj_name'):
    name = getattr(options, attr, '')
    if name and Path(str(name) + '.ms').is_dir():
      return str(name) + '.ms'
  return ''


def _unflagged_visibilities(vis, options):
  """{antenna name: unflagged visibility count}, from a flagdata summary.

  Counted over the calibrator fields only, mirroring hif_refant's restriction to
  calibration-intent scans: the refant matters for the solve, and the target may
  barely be present in a calibrator-heavy track.
  """
  if not vis:
    return {}
  try:
    summary = ct.flagdata(vis=vis, mode='summary', field=_calibrator_fields(options),
                          spwchan=False, basecnt=False)
    per_antenna = (summary or {}).get('antenna') or {}
  except Exception as exc:
    print(f"find_refant: could not read flag statistics from {vis} ({exc}); "
          f"ranking on distance alone.")
    return {}
  counts = {}
  for name, entry in per_antenna.items():
    try:
      total, flagged = float(entry['total']), float(entry['flagged'])
    except (KeyError, TypeError, ValueError):
      continue
    counts[name] = max(total - flagged, 0.0)
  return counts


def _calibrator_fields(options:options_class.Options):
  """Comma-separated calibrator field names, or '' for every field."""
  names = []
  for attr in ('flux_cal', 'phase_cal'):
    cal = getattr(options, attr, None)
    name = getattr(cal, 'listobs_name', '') if cal else ''
    if name and name not in names:
      names.append(str(name))
  return ','.join(names)

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
    run_log.note('CALIBRATION', f"applymode ({Path(caltable).name})",
                 "calflag (default -- failure rate could not be read)")
    return 'calflag'
  pct = rate * 100
  mode = 'calonly' if pct > GAINCAL_APPLYMODE_CUTOFF_PCT else 'calflag'
  note = "  <-- high: solint may be too short / SNR too low / refant poor" if pct > GAINCAL_WARN_PCT else ""
  print(f"gaincal failure rate {pct:.1f}% ({Path(caltable).name}) -> applymode='{mode}'{note}")
  run_log.note('CALIBRATION', f"applymode ({Path(caltable).name})",
               f"{mode}   (gaincal failure rate {pct:.1f}%"
               f"{', high' if pct > GAINCAL_WARN_PCT else ''})")
  return mode

def phase_self_calibration(options:options_class.Options):
  '''perform self cal on phase calibrator'''#do normal cal just without a phase cal field
  pass

