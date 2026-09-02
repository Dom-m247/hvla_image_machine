"""Tar the finished run into the bundles the archive form asks you to attach.

Two, deliberately: the products bundle is small enough to upload and holds
everything a reviewer reads (FITS, pbcor, PNG, fit record, run log, replay), while
the calibrated MS is a separate, much larger file nobody wants to wait on to get
the first one. Mirrors 1.99's pbcor_tar / _CALMS split.

    products, ms = results_package.package(options)
"""
import shutil
import tarfile
from pathlib import Path

from classes import run_log

PRODUCTS_SUFFIX = '_results.tar.gz'
MS_SUFFIX = '_CALMS.tar.gz'


def package(options, include_ms=True):
    """Tar the results folder, and the calibrated MS beside it. Returns
    (products_path, ms_path); either is None when there was nothing to tar.

    Best-effort throughout: packaging must never lose a finished image."""
    results_dir = Path(str(getattr(options, 'results_dir', '') or ''))
    name = str(getattr(options, 'results_name', '') or 'run')
    if not results_dir.is_dir():
        print("package: no results folder to tar (collect_results did not run).")
        return None, None

    products = _tar_products(results_dir, name)
    ms = _tar_ms(options, results_dir, name) if include_ms else None
    return products, ms


def _tar_products(results_dir, name):
    """The results folder as <name>_results.tar.gz, written inside it."""
    dest = results_dir / f"{name}{PRODUCTS_SUFFIX}"
    try:
        #the tarball lives in the folder it archives, so skip any .tar.gz on the way
        #in -- including this one, mid-write
        with tarfile.open(dest, 'w:gz') as tar:
            tar.add(results_dir, arcname=name, filter=_skip_tarballs)
    except Exception as exc:
        print(f"package: could not build {dest.name}: {exc}")
        return None
    _report(dest, 'products')
    return dest


def _tar_ms(options, results_dir, name):
    """The calibrated MS as <name>_CALMS.tar.gz, written beside the products tar."""
    ms = Path(str(getattr(options, 'calibrated_filename', '') or '') + '.ms')
    if not ms.is_dir():
        print(f"package: no calibrated MS at {ms}; skipping the MS bundle.")
        return None
    dest = results_dir / f"{name}{MS_SUFFIX}"
    print(f"package: taring {ms.name} ({_size(_tree_bytes(ms))}) -- this can take a while ...")
    try:
        with tarfile.open(dest, 'w:gz') as tar:
            tar.add(ms, arcname=f"{name}.ms")
    except Exception as exc:
        print(f"package: could not build {dest.name}: {exc}")
        dest.unlink(missing_ok=True)  #a half-written bundle is worse than none
        return None
    _report(dest, 'calibrated MS')
    return dest


def _skip_tarballs(info: tarfile.TarInfo):
    """Drop .tar.gz members, so a bundle never contains itself or a previous run's."""
    return None if info.name.endswith('.tar.gz') else info


def _tree_bytes(path):
    """Total size of a directory tree, in bytes."""
    return sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())


def _size(num):
    """Bytes as a short human-readable string."""
    for unit in ('B', 'KB', 'MB', 'GB'):
        if num < 1024 or unit == 'GB':
            return f"{num:.0f}{unit}" if unit == 'B' else f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}GB"


def _report(path, what):
    """Print and log a finished bundle."""
    size = _size(path.stat().st_size)
    print(f"Packaged {what}: {path} ({size})")
    run_log.note('OUTPUT', f"{what} bundle", f"{path.name} ({size})")
