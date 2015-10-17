from __future__ import absolute_import, division, print_function, unicode_literals
import sys
sys.path.insert(0, '../..')
from pato.container import Container

c = Container()
c['pato/container'] = c
c.load_yaml_file('myconf.yaml')
obj = c['dynamic/object']
print(obj.foo)
