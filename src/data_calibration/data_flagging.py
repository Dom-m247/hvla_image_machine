"""Data-flagging breakpoint: tfcrop RFI autoflagging with a reversible backup and a
plotms visual check, run on the pre-calibration MS before gaincal/bandpass.

Mirrors the flagging step in user_script_1.99.py, but wraps it so the user can accept
the result or roll it back: the current flags are saved as a named flag version first,
so a rejected tfcrop pass is undone with flagmanager restore (no re-split needed).
"""
import os

import casatasks as ct
from casaplotms import plotms

from classes.CLI_input import CLI
from classes import decisions, run_log
from classes.constants import VERIFY
from pre_calibration.options_class import Options

#named flag version saved before tfcrop so the pass is fully reversible
FLAG_BACKUP_VERSION = 'before_tfcrop'


def manual_flagging(options: Options):
    """Run the data-flagging breakpoint on the calibration MS.

    Steps: back up current flags -> tfcrop autoflag -> plotms amp-vs-time check ->
    block for the user to accept or revert. plotms opens a non-blocking GUI and
    returns immediately, so the accept/revert prompt is what actually holds the
    pipeline until the user has looked at the plot.
    """
    vis = options.initial_calibration_filename + '.ms'
    print("\n" + "=" * 60)
    print(" Data flagging breakpoint (tfcrop)")
    print("=" * 60)

    #1) Back up the current flags so tfcrop is fully reversible.
    _reset_flag_version(vis, FLAG_BACKUP_VERSION)
    ct.flagmanager(vis=vis, mode='save', versionname=FLAG_BACKUP_VERSION)
    print(f"Saved flag backup '{FLAG_BACKUP_VERSION}' for {vis}")

    #2) tfcrop RFI autoflagging: pre-calibration, on the DATA column, all fields.
    #   flagbackup=False because we just took our own named backup above.
    print("Running tfcrop autoflagging ...")
    ct.flagdata(vis=vis, mode='tfcrop', datacolumn='data',
                field='', correlation='', action='apply', flagbackup=False)

    #3) plotms check. Only 'verify' opens the GUI -- there is nobody watching an
    #   'auto' run, and a window it never closes would just sit there. The PNG is
    #   written either way, so the pass is reviewable after the fact.
    review = decisions.mode(options, 'flagging') == VERIFY
    _show_plotms(vis, options.initial_calibration_filename + '_tfcrop_check.png', gui=review)

    #4) Catch: block until the user accepts the flagging or reverts to the pre-flag
    #   state. Without this the pipeline would race past the non-blocking plotms.
    #   'auto' keeps the pass unreviewed; the backup is still taken either way.
    if not review:
        print("Flagging applied (auto); resuming calibration.")
        run_log.note('CALIBRATION', 'Flagging', 'tfcrop applied automatically (not reviewed)')
    elif CLI.getYesNo("Keep this flagging? (n = revert to the pre-flag state)"):
        print("Flagging accepted; resuming calibration.")
        run_log.note('CALIBRATION', 'Flagging', 'tfcrop applied and accepted by the user')
        run_log.event(f"tfcrop autoflagging accepted on {vis}")
    else:
        ct.flagmanager(vis=vis, mode='restore', versionname=FLAG_BACKUP_VERSION)
        print(f"Reverted: restored flags from '{FLAG_BACKUP_VERSION}'; resuming calibration.")
        run_log.note('CALIBRATION', 'Flagging',
                     f"tfcrop applied then REVERTED (restored '{FLAG_BACKUP_VERSION}')")
        run_log.event(f"tfcrop autoflagging reverted on {vis}")


def _show_plotms(vis, plotfile, gui=True):
    """plotms amp-vs-time check coloured by field. The GUI opens only when `gui` is
    set AND $DISPLAY exists (so a headless run doesn't hang waiting on X); the PNG is
    written either way. Any plotms failure is non-fatal."""
    have_display = gui and bool(os.environ.get('DISPLAY'))
    try:
        plotms(vis=vis, xaxis='time', yaxis='amp', coloraxis='field',
               plotfile=plotfile, overwrite=True, highres=True, showgui=have_display)
        where = "opened plotms GUI; " if have_display else ""
        print(f"{where}wrote flagging check plot: {plotfile}")
    except Exception as exc:
        print(f"plotms check failed ({exc}); inspect {vis} manually before deciding.")


def _reset_flag_version(vis, versionname):
    """Delete an existing flag version of this name (ignored if absent) so the fresh
    save snapshots the current pre-tfcrop state instead of failing on a duplicate."""
    try:
        ct.flagmanager(vis=vis, mode='delete', versionname=versionname)
    except Exception:
        pass
