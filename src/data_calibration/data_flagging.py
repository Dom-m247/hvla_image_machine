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

    #3) plotms visual check. Show a GUI when a display exists (non-blocking), and
    #   always write a PNG so there is a durable artifact even headless.
    _show_plotms(vis, options.initial_calibration_filename + '_tfcrop_check.png')

    #4) Catch: block until the user accepts the flagging or reverts to the pre-flag
    #   state. Without this the pipeline would race past the non-blocking plotms.
    if CLI.getYesNo("Keep this flagging? (n = revert to the pre-flag state)"):
        print("Flagging accepted; resuming calibration.")
    else:
        ct.flagmanager(vis=vis, mode='restore', versionname=FLAG_BACKUP_VERSION)
        print(f"Reverted: restored flags from '{FLAG_BACKUP_VERSION}'; resuming calibration.")


def _show_plotms(vis, plotfile):
    """Open a plotms amp-vs-time check coloured by field. GUI only when $DISPLAY is
    set (so a headless run doesn't hang waiting on X); the PNG is written either way.
    Any plotms failure is non-fatal -- the user can still accept/revert below."""
    have_display = bool(os.environ.get('DISPLAY'))
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
