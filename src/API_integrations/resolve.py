'''Name -> position, the one place a typed source name is looked up.

SIMBAD first: its name database is the broader one, and radio_search2 resolves
names through SIMBAD, so a name that resolves here is one the archive search can
use. NED is the fallback for names only it knows (it then supplies its own
preferred name as the alias, which radio_search2 may still not know).'''
from API_integrations.simbad import simbad


def resolve_source(source_name):
  '''{'ra_decl': {'ra', 'decl'}, 'alias', 'redshift', 'resolver'} or False.'''
  if result := simbad.resolve(source_name):
    result['resolver'] = 'SIMBAD'
    return result
  from API_integrations.NED import NED_API   #lazy: only needed for SIMBAD misses
  if result := NED_API.obj_exists(source_name):
    print(f"SIMBAD does not know '{source_name}'; using NED's position "
          f"(NED name '{result['alias']}')")
    result['resolver'] = 'NED'
    return result
  return False
