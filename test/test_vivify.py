from __future__ import absolute_import, division, print_function, unicode_literals
import pato.vivify

def test_refresh(c, monkeypatch):
    c.load_yaml("""
a:
  :: object
f:
  :: pato.vivify.Factory
  container: <pato/container>
  key: a
  validity: 10
""")
    c["pato/container"] = c

    t = 1000
    monkeypatch.setattr(pato.vivify.time, 'time', lambda: t)
    f = c["f"]
    
    o1 = f()
    o2 = f()
    assert o2 is o1
    assert f.expires == 1010

    t = 1005
    o2 = f()
    assert o2 is o1
    assert f.expires == 1010

    t = 1010
    o2 = f()
    assert o2 is not o1
    assert f.expires == 1020

    t = 1015
    o3 = f()
    assert o3 is o2
    assert f.expires == 1020
