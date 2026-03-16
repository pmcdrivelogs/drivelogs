import sys
try:
    import pkg_resources
    import apscheduler
    print('OK')
    print('pkg_resources:', pkg_resources.__file__)
    try:
        from apscheduler import __version__ as aps_version
    except Exception:
        try:
            aps_version = apscheduler.__version__
        except Exception:
            aps_version = 'unknown'
    print('apscheduler version:', aps_version)
except Exception as e:
    print('ERROR', e, file=sys.stderr)
    raise
