"""Full-Auto: the single most sensitive observation of each target, fully automatic."""
from ..selection import attended_only, within_size

NAME = 'full-auto'
DEFAULT_PRESET = 'full_auto'
HELP = 'the deepest observation of each source, fully automatic'
DEFAULT_OPTIONS = {
  'all_obs': False,   #run every runnable observation, not just the deepest
}


def choose(selector, target, options):
  selections, rejected = selector.select_all(
    target.name, target.projects or options['projects'], options['bands'])
  #an experimental band only runs attended, and the size cap applies before picking:
  #the deepest segment that can run wins
  selections, held = attended_only(selections, options['attended'])
  selections, too_big = within_size(selections, options['max_gb'])
  if not options['all_obs']:
    selections = selections[:1]
  return selections, rejected + held + too_big
