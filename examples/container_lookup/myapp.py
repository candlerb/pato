from __future__ import absolute_import, division, print_function, unicode_literals

class Dynamic(object):
    def __init__(self, container):
        self.container = container
        self.foo = container['dynamic/username']
        self.bar = container['dynamic/password']
