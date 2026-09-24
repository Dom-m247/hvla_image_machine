"""The harness kinds a sweep can be: each decides which observations of a target run.

A kind is a module with NAME, DEFAULT_PRESET, DEFAULT_OPTIONS (its own knobs, on
top of presets.COMMON_OPTIONS) and choose(selector, target, options) ->
(selections, rejected). Searching, downloading, seeding and running are shared.
"""
from . import full_auto, lightcurve

KINDS = {kind.NAME: kind for kind in (full_auto, lightcurve)}
