"""
Basic utilities for request-local variables. For a fuller
implementation see `flask.globals` which in turn uses `werkzeug.local`
"""

from __future__ import absolute_import, division, print_function, unicode_literals
from contextlib import contextmanager

SENTINEL = object()

def local_factory():
    """
    Return a context object on which attributes can be set; these will
    will be distinct for each thread or greenlet.
    """
    try:
        import werkzeug.local
        return werkzeug.local.Local()
    except ImportError:
        import threading
        return threading.local()

ctx = local_factory()

@contextmanager
def setattrs(local=ctx, **overrides):
    """
    A context manager for setting attribtues for the duration of a
    request, and removing them afterwards.  Supports recursive use.

    local = local_factory()
    ...
    with setattrs(local, db_session=X, workflow_id=Y):
        ... do stuff
    """
    prev = {}
    for key in overrides:
        prev[key] = getattr(local, key, SENTINEL)
        setattr(local, key, overrides[key])
    try:
        yield local
    finally:
        for key in overrides:
            if prev[key] is SENTINEL:
                delattr(local, key)
            else:
                setattr(local, key, prev[key])
