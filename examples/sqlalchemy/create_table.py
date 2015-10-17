from __future__ import absolute_import, division, print_function, unicode_literals
import sys
sys.path.insert(0, '../..')
from pato.container import Container

c = Container()
c.load_yaml_file('myapp.yaml')
manager = c['db/manager']
manager(c['myapp/setup'].setup)
