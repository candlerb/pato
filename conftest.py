from __future__ import absolute_import, division, print_function, unicode_literals
from pato.container import Container
from pytest import fixture

@fixture
def c():
    return Container()
