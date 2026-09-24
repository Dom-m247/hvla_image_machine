"""Lightcurve Generator: every observation pointed near the target, oldest first.

Each epoch is imaged with the same preset, so the images are comparable. The
base preset fixes the imaging parameters; the deep one cleans interactively and
runs attended. After every pass the epochs' source fits are plotted over time
(lightcurve_plot).
"""
from .. import lightcurve_plot
from ..selection import observation_date, within_size

NAME = 'lightcurve'
DEFAULT_PRESET = 'lightcurve'
HELP = 'every observation within max_sep_arcsec of each source, in date order'
DEFAULT_OPTIONS = {
  'max_sep_arcsec': 100.0,   #pointing offset from the source an epoch may have
}


def choose(selector, target, options):
  selections, rejected = selector.select_all(
    target.name, target.projects or options['projects'], options['bands'],
    max_sep_arcsec=options['max_sep_arcsec'])
  selections, too_big = within_size(selections, options['max_gb'])
  return sorted(selections, key=observation_date), rejected + too_big


def summarize(sweep):
  return lightcurve_plot.build(sweep)
