from __future__ import annotations

from classes.constants import *
import casatasks as ct
from pre_calibration import options_class
from classes import *
import pprint as pp
from data_calibration import parse_listobs as parse

from pathlib import Path


def amp_phase_cal(options:options_class.Options):
  """
  Performs initial calibration on phase calibrator and source
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
                                  field=options.amp_cal.name,
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
                               field=options.amp_cal.name,
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
                            field=options.phase_cal.name,
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
                            reference=[options.amp_cal.name], #fluxdensity model calibrator
                            transfer=[options.phase_cal.name], #nodder,
                            incremental=False
   )
  
  if not Path(CALIBRATED_MS+'ms').is_dir():
    print(f"applying calibrations to {options.initial_calibration_filename+'.ms'}'s name : {options.source_ids.name} field ID: {options.source_ids.initial_ms_fieldID}")
    apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
           field= options.amp_cal.name ,
           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
           gainfield=[options.amp_cal.name,''],
           interp=['nearest',''], #['nearest','linear']?
           calwt=[False], #true?
    )
    apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
           field= options.phase_cal.name ,
           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
           gainfield=[options.phase_cal.name,''],
           interp=['nearest',''], #['nearest','linear']?
           calwt=[False], #true?
    )
    apply_cal_out = ct.applycal(vis=options.initial_calibration_filename+'.ms',
           field=options.source_ids.name,
           gaintable=[options.initial_calibration_filename+FLUXSCALE_X+'1',options.initial_calibration_filename+BANDPASS_B0],
           gainfield=[options.phase_cal.name,''],
           interp=['linear',''], #['nearest','linear']?
           calwt=[False], #true?
    )

  #return to data_data_cal and split of callibrated data
  
def self_cal_cycle(options:options_class.Options,cycle_number,solint='inf'):
  '''
  Perform one cycle of self calibration with 
  '''
  find_refant(options) #do again incase it's starting with a calibrated dataSet
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

