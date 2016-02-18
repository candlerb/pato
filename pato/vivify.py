"""
Sometimes, having a persistent object created once at the start of your
application is not sufficient.  For example, say it logs into a remote
service but the API key has a limited lifetime; over the lifetime of the
application you need a new object.  But the credentials needed to log in
again are stored in the container, not in the object itself.

This could probably be done by some fancy proxy object, but here I just
provide a simple caching factory.  Each time you call factory() it will
either give you the current object, or force the container to create a
new one.

Example:

    # This is the object which has a limited lifetime
    salesforce:
      :: simple_salesforce.Salesforce
      username: ...
      password: ...
      security_token: ...
      sandbox: ...

    # This is the wrapper which returns a cached or new object
    salesforce/factory:
      :: pato.vivify.Factory
      container: <pato/container>
      key: salesforce
      validity: 7200

    app:
      :: Myapp
      sf_factory: <salesforce/factory>

    ...

class Myapp(object):
  def __init__(self, sf_factory):
    self.sf_factory = sf_factory

  def __call__(self, args):
    sf = self.sf_factory()
    ... do stuff with sf object
"""

from __future__ import absolute_import, division, print_function, unicode_literals
import time

class Factory(object):
    """
    This class returns an object when called.

    If the object has expired, then a new instance is created.

    It's basically a caching object factory, and it relies on the
    underlying pato.container to create a fresh object when required.
    """
    def __init__(self, container, key, validity=3600):
        self.container = container
        self.key = key
        self.validity = validity
        self.expires = None

    def __call__(self):
        if not self.expires:
            self.expires = time.time() + self.validity
        elif time.time() >= self.expires:
            try:
                del self.container[self.key]
            except KeyError:
                pass
            self.expires = time.time() + self.validity
        return self.container[self.key]
