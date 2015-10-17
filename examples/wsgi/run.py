from __future__ import absolute_import, division, print_function, unicode_literals
from wsgiref.simple_server import make_server
import sys
sys.path.insert(0, '../..')
from pato.container import Container

c = Container()
c.load_yaml_file('myapp.yaml')
app = c['app']

httpd = make_server('', 4567, app)
print("Point your browser at http://localhost:4567")
httpd.serve_forever()
