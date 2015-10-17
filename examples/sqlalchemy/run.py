from __future__ import absolute_import, division, print_function, unicode_literals
import sys
sys.path.insert(0, '../..')
from pato.container import Container

c = Container()
c.load_yaml_file('myapp.yaml')

manager = c['db/manager']
foo = c['myapp/foo']

print("*** The following is all in one transaction")
with manager():
    foo.insert(123)
    foo.insert_twice(456)
    res = foo.list()
    print(repr(res))

print("*** The following are in separate sessions/transactions")
manager.invoke(foo.insert, 123)
manager.invoke(foo.insert_twice, 456)
res = manager.invoke(foo.list)
print(repr(res))
