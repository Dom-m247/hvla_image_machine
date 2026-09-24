"""Full-Auto: the single most sensitive observation of each target, fully automatic."""
from ..selection import within_size

NAME = 'full-auto'
DEFAULT_PRESET = 'full_auto'
HELP = 'the deepest observation of each source, fully automatic'
DEFAULT_OPTIONS = {
  'all_obs': False,   #run every runnable observation, not just the deepest
}


def choose(selector, target, options):
  selections, rejected = selector.select_all(
    target.name, target.projects or options['projects'], options['bands'])
  #the size cap applies before picking, so the deepest segment that fits wins
  selections, too_big = within_size(selections, options['max_gb'])
  if not options['all_obs']:
    selections = selections[:1]
  return selections, rejected + too_big
