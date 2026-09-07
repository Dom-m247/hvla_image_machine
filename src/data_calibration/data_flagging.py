"""Data flagging: a selectable set of flagdata passes, run in two stages.

Pre-calibration on the split calibration MS (DATA), and post-calibration on the
calibrated target (rflag, which needs the CORRECTED-derived data a DATA pass cannot
see). Each stage saves a named flag version first, so the whole stage is reversible
with flagmanager restore.
"""
import os

import casatasks as ct
from casaplotms import plotms

from classes.CLI_input import CLI
from classes import decisions, run_log
from classes.constants import (VERIFY, MANUAL, FLAG_CLIPZEROS, FLAG_QUACK, FLAG_SHADOW,
                               FLAG_AUTOCORR, FLAG_TFCROP, FLAG_EXTEND, FLAG_RFLAG,
                               FLAG_QUACK_INTERVAL, FLAG_EXTEND_GROWTIME,
                               FLAG_RFLAG_TIMEDEVSCALE)
from pre_calibration.options_class import Options

#named flag versions, one per stage, so each reverts independently
PRE_CAL_BACKUP = 'before_flagging'
POST_CAL_BACKUP = 'before_rflag'

#which methods run in which stage, in that stage's order: extend grows what the
#autoflagger of that stage just found, so it always follows it
PRE_CAL_METHODS = (FLAG_CLIPZEROS, FLAG_QUACK, FLAG_SHADOW, FLAG_AUTOCORR,
                   FLAG_TFCROP, FLAG_EXTEND)
POST_CAL_METHODS = (FLAG_RFLAG, FLAG_EXTEND)


def pre_calibration_flagging(options: Options):
    """Flag the calibration MS before gaincal/bandpass, on the DATA column."""
    chosen = options.flag_methods()
    methods = [m for m in PRE_CAL_METHODS if m in chosen]
    selection = _manual_selection(options)
    _run_stage(options, vis=options.initial_calibration_filename + '.ms',
               methods=methods, backup=PRE_CAL_BACKUP, stage='pre-cal',
               selection=selection)


def post_calibration_flagging(options: Options):
    """Flag the calibrated target MS. The split wrote CORRECTED into its DATA column,
    so rflag's noise statistics see calibrated data here."""
    chosen = options.flag_methods()
    methods = [m for m in POST_CAL_METHODS if m in chosen]
    if FLAG_RFLAG not in methods:
        return  #extend alone has nothing to grow at this stage
    selection = options.flag_selection or {}
    #the calibrated MS holds one field, so only the spw half of a manual selection applies
    _run_stage(options, vis=options.calibrated_filename + '.ms',
               methods=methods, backup=POST_CAL_BACKUP, stage='post-cal',
               selection={'spw': selection.get('spw', '')})


def _run_stage(options: Options, vis, methods, backup, stage, selection):
    """Back up the flags, run `methods` in order measuring each, show the check plot,
    then let the user accept or revert the whole stage."""
    if not methods and not selection.get('outright'):
        return
    field, spw = selection.get('field', ''), selection.get('spw', '')
    print("\n" + "=" * 60)
    print(f" Data flagging ({stage}): {', '.join(methods) or 'manual selection only'}")
    print("=" * 60)

    _reset_flag_version(vis, backup)
    ct.flagmanager(vis=vis, mode='save', versionname=backup)
    print(f"Saved flag backup '{backup}' for {vis}")

    start = _flagged_fraction(vis)
    steps = []
    if selection.get('outright'):
        _flag_manual(vis, field, spw)
        steps.append(('manual', start, _flagged_fraction(vis)))
    for method in methods:
        before = steps[-1][2] if steps else start
        print(f"Running {method} ...")
        _METHODS[method](vis, field, spw)
        steps.append((method, before, _flagged_fraction(vis)))

    #an imported replay has nobody to review it; the backup is still taken either way
    review = (decisions.mode(options, 'flagging') in (VERIFY, MANUAL)
              and decisions.is_interactive(options))
    plotfile = f"{vis[:-3]}_{stage.replace('-', '_')}_flag_check.png"
    _show_plotms(vis, plotfile, gui=review)
    summary = _summary(steps, start)
    print("  " + "\n  ".join(summary))

    #plotms opens a non-blocking GUI, so this prompt is what holds the pipeline
    #until the user has actually looked at the plot
    if not review:
        print("Flagging applied (auto); resuming.")
        _record(stage, summary, 'applied automatically (not reviewed)')
    elif CLI.getYesNo("Keep this flagging? (n = revert to the pre-flag state)"):
        print("Flagging accepted; resuming.")
        _record(stage, summary, 'applied and accepted by the user')
        run_log.event(f"flagging accepted on {vis}")
    else:
        #the deltas describe flags that no longer exist, so they are not recorded
        ct.flagmanager(vis=vis, mode='restore', versionname=backup)
        print(f"Reverted: restored flags from '{backup}'; resuming.")
        run_log.note('CALIBRATION', f"Flagging ({stage})", f"REVERTED (restored '{backup}')")
        run_log.event(f"flagging reverted on {vis}")


def _manual_selection(options: Options):
    """The flagging 'manual' mode: which fields and spws to act on, and whether to flag
    them outright. Returns {} for every other mode."""
    if decisions.mode(options, 'flagging') != MANUAL:
        return {}
    if recorded := decisions.resolved(options, 'flag_selection'):
        print(f"  flag selection (recorded): {recorded}")
        return recorded
    if not decisions.is_interactive(options):
        return {}

    #post-split names/ids: the calibrator split renumbers both
    fields = list(getattr(options.init_data, 'fields', []) or [])
    spws = list(getattr(options.init_data, 'spectral_windows', []) or [])
    chosen_fields = decisions.pick_many('Flag which fields?', fields,
                                        formatter=lambda f: f"{f.name}  (id {f.id})")
    chosen_spws = decisions.pick_many('Flag which spectral windows?', spws,
                                      formatter=lambda s: f"spw {s.id}  {s.ctrfreq_mhz} MHz, "
                                                          f"{s.num_channels} chan")
    selection = {
        'field': _selection_csv(chosen_fields, fields, 'name'),
        'spw': _selection_csv(chosen_spws, spws, 'id'),
        'outright': decisions.confirm(
            "Flag this selection outright? (n = run the selected methods restricted to it)"),
    }
    options.flag_selection = selection  #recorded for replay
    decisions.announce('flagging', MANUAL,
                       f"field={selection['field'] or 'all'} spw={selection['spw'] or 'all'}")
    return selection


def _selection_csv(chosen, available, attr):
    """CSV of the picks. Everything picked -- or nothing -- gives '', which is how
    CASA reads 'all' anyway."""
    if not chosen or len(chosen) == len(available):
        return ''
    return ','.join(str(getattr(c, attr)) for c in chosen)


def _flag_clipzeros(vis, field='', spw=''):
    ct.flagdata(vis=vis, mode='clip', clipzeros=True, datacolumn='data', field=field,
                spw=spw, action='apply', flagbackup=False)


def _flag_quack(vis, field='', spw=''):
    ct.flagdata(vis=vis, mode='quack', quackinterval=FLAG_QUACK_INTERVAL, quackmode='beg',
                field=field, spw=spw, action='apply', flagbackup=False)


def _flag_shadow(vis, field='', spw=''):
    ct.flagdata(vis=vis, mode='shadow', field=field, spw=spw,
                action='apply', flagbackup=False)


def _flag_autocorr(vis, field='', spw=''):
    ct.flagdata(vis=vis, mode='manual', autocorr=True, field=field, spw=spw,
                action='apply', flagbackup=False)


def _flag_tfcrop(vis, field='', spw=''):
    ct.flagdata(vis=vis, mode='tfcrop', datacolumn='data', field=field, spw=spw,
                correlation='', action='apply', flagbackup=False)


def _flag_extend(vis, field='', spw=''):
    ct.flagdata(vis=vis, mode='extend', field=field, spw=spw, extendpols=True,
                growtime=FLAG_EXTEND_GROWTIME, action='apply', flagbackup=False)


def _flag_rflag(vis, field='', spw=''):
    """Post-calibration outlier pass. Every spw here is 1 channel, so this fits in
    time only -- freqdevscale has no axis to work on."""
    ct.flagdata(vis=vis, mode='rflag', datacolumn='data', field=field, spw=spw,
                timedevscale=FLAG_RFLAG_TIMEDEVSCALE, action='apply', flagbackup=False)


def _flag_manual(vis, field='', spw=''):
    ct.flagdata(vis=vis, mode='manual', field=field, spw=spw,
                action='apply', flagbackup=False)


_METHODS = {FLAG_CLIPZEROS: _flag_clipzeros, FLAG_QUACK: _flag_quack,
            FLAG_SHADOW: _flag_shadow, FLAG_AUTOCORR: _flag_autocorr,
            FLAG_TFCROP: _flag_tfcrop, FLAG_EXTEND: _flag_extend,
            FLAG_RFLAG: _flag_rflag}


def _flagged_fraction(vis):
    """Flagged fraction of `vis` as a percentage, or None if it can't be measured."""
    try:
        summary = ct.flagdata(vis=vis, mode='summary', spwchan=False, basecnt=False) or {}
        total = float(summary.get('total', 0))
        return 100.0 * float(summary['flagged']) / total if total else None
    except Exception as exc:
        print(f"could not measure the flagged fraction ({exc})")
        return None


def _summary(steps, start):
    """Per-method flagged-fraction deltas, so an automatic pass is auditable."""
    if not steps:
        return ['no methods ran']
    return [f"{_pct(start)} -> {_pct(steps[-1][2])} flagged ({_delta(start, steps[-1][2])})"] + \
           [f"{name:<10}{_pct(before)} -> {_pct(after)}  ({_delta(before, after)})"
            for name, before, after in steps]


def _record(stage, summary, outcome):
    """Write the deltas to the run log, headline first, then the per-method rows."""
    run_log.note('CALIBRATION', f"Flagging ({stage})", f"{summary[0]}, {outcome}")
    for row in summary[1:]:
        run_log.note('CALIBRATION', '', row)


def _pct(value):
    return '     ?' if value is None else f"{value:5.1f}%"


def _delta(before, after):
    if before is None or after is None:
        return '?'
    return f"{after - before:+.1f}"


def _show_plotms(vis, plotfile, gui=True):
    """plotms amp-vs-time check coloured by field. The GUI opens only when `gui` is
    set AND $DISPLAY exists (so a headless run doesn't hang waiting on X); the PNG is
    written either way. Any plotms failure is non-fatal."""
    have_display = gui and bool(os.environ.get('DISPLAY'))
    #a PNG-only render still maps a Qt window for a moment on a live display -- the
    #window that flashes up and vanishes. Force Qt offscreen so nothing appears.
    previous = os.environ.get('QT_QPA_PLATFORM')
    if not have_display:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    try:
        plotms(vis=vis, xaxis='time', yaxis='amp', coloraxis='field',
               plotfile=plotfile, overwrite=True, highres=True, showgui=have_display)
        where = "opened plotms GUI; " if have_display else ""
        print(f"{where}wrote flagging check plot: {plotfile}")
    except Exception as exc:
        print(f"plotms check failed ({exc}); inspect {vis} manually before deciding.")
    finally:
        if not have_display:
            if previous is None:
                os.environ.pop('QT_QPA_PLATFORM', None)
            else:
                os.environ['QT_QPA_PLATFORM'] = previous


def _reset_flag_version(vis, versionname):
    """Delete an existing flag version of this name (ignored if absent) so the fresh
    save snapshots the current state instead of failing on a duplicate."""
    try:
        ct.flagmanager(vis=vis, mode='delete', versionname=versionname)
    except Exception:
        pass
