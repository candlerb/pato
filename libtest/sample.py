from __future__ import absolute_import, division, print_function, unicode_literals

def adder(x, y):
    """A test factory function"""
    return x+y

class Foo(object):
    """A test class with constructor and class method"""
    def __init__(self, username, password):
        self.creds = username+":"+password

    @classmethod
    def my_class_method(cls, username):
        return cls(username, password="fixed")

    @staticmethod
    def bad_factory():
        raise RuntimeError("Bleurgh")

class Bar(object):
    def __init__(self, x, y, z="defvalue"):
        self.x = x
        self.y = y
        self.z = z
