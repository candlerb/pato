from __future__ import absolute_import, division, print_function, unicode_literals
from pato.container import Container
from pytest import raises
import libtest.sample
from six.moves.queue import Queue
from threading import Thread

def test_simple_values(c):
    c.load_yaml("""
a: ""
b: hello
c: 123
d: null
""")
    assert c['a'] == ""
    assert c['b'] == "hello"
    assert c['c'] == 123
    assert c['d'] is None

def test_service_alias(c):
    c.load_yaml("""
a: ""
b: <<foo>
c: <d>
d: wibble
""")
    assert c['a'] == ""
    assert c['b'] == "<foo>"
    assert c['c'] == "wibble"
    assert c['d'] == "wibble"
    assert c['c'] is c['d']

def test_resolve_recursive(c):
    c.load_yaml("""
a: "hello"
b: "world"
c:
    arg1: <a>
    arg2:
        arg2b: <b>
d:
    - <b>
    - <c>
    - the end
""")
    assert not c.services
    assert c['c'] == {
        "arg1": "hello",
        "arg2": {
            "arg2b": "world",
        },
    }
    assert c['d'] == [c['b'], c['c'], "the end"]

def test_resolve_all(c):
    c.load_yaml("""
a: "hello"
b: "world"
c: [<a>, <b>]
""")
    for k in ['a', 'b', 'c']:
        assert k not in c.services
    res = c.resolve_all()
    for k in ['a', 'b', 'c']:
        assert k in res
    assert c['c'] == [c['a'], c['b']]

def test_override(c):
    c.load_yaml("""
a: "hello"
b: "world"
""")
    c.resolve_all()
    c.load_yaml("""
a: "goodbye"
""")
    assert c['a'] == "goodbye"
    assert c['b'] == "world"

def test_resolve_objects(c):
    c.load_yaml("""
a:
    # class within a module
    :: libtest.sample.Foo
    username: abc
    password: xyz
b:
    # factory function within a module
    :: libtest.sample.adder
    x: <x>
    y: <y>
c:
    # class method
    :: libtest.sample.Foo.my_class_method
    username: def
x: 10
y: 20
""")
    assert isinstance(c['a'], libtest.sample.Foo)
    assert c['a'].creds == "abc:xyz"
    assert c['b'] == 30
    assert c['c'].creds == "def:fixed"

def test_expire(c):
    c.load_yaml("""
a:
    :: libtest.sample.Foo
    username: abc
    password: xyz
b:
    :: libtest.sample.Foo
    username: def
    password: uvw
""")
    assert 'a' in c
    assert 'b' in c
    a1 = c['a']
    b1 = c['b']
    del c['a']
    assert 'a' in c
    assert 'b' in c
    a2 = c['a']
    b2 = c['b']
    assert a1 is not a2
    assert b1 is b2
    c.expire()
    assert 'a' in c
    assert 'b' in c
    a3 = c['a']
    b3 = c['b']
    assert a2 is not a3
    assert b2 is not b3

def test_alternate_key():
    c = Container(factory_key="pato/factory")
    c.load_yaml("""
a:
    pato/factory: libtest.sample.Foo
    username: abc
    password: xyz
""")
    assert c['a'].creds == "abc:xyz"

def test_splat_args(c):
    c.load_yaml("""
a:
    # all splat args
    :: libtest.sample.Foo
    =: [abc, def]
b:
    # mixture of splat and kwargs; single-element list
    :: libtest.sample.Foo
    =: ghi
    password: jkl
c:
    # indirect list
    :: libtest.sample.Foo
    =: <creds>
creds:
  - mno
  - pqr
""")
    assert isinstance(c['a'], libtest.sample.Foo)
    assert c['a'].creds == "abc:def"
    assert c['b'].creds == "ghi:jkl"
    assert c['c'].creds == "mno:pqr"

def test_resolve_builtin(c):
    c.load_yaml("""
a:
    :: libtest.sample.Foo
    username: abc
    password: xyz
b:
    :: getattr
    =: [<a>, creds]
c:
    :: libtest.sample.Bar
    x: 100
    y: 200
d:
    <c>.x
""")
    assert c['b'] == "abc:xyz"
    assert c['d'] == 100

def test_import_name(c):
    c.load_yaml("""
a:
    :: pato.container.import_name
    =: libtest.sample
b:
    :: pato.container.import_name
    =: libtest.sample.adder
""")
    assert c['a'] is libtest.sample
    assert c['b'] is libtest.sample.adder

def test_service_as_factory(c):
    c['my_factory'] = libtest.sample.Foo
    c.load_yaml("""
factory2: <my_factory>
a:
    :: <my_factory>
    username: abc
    password: xyz
b:
    :: <factory2>
    username: def
    password: uvw
""")
    assert c['a'].creds == "abc:xyz"
    assert c['b'].creds == "def:uvw"

def test_nested_anonymous_objects(c):
    c.load_yaml("""
a:
    :: libtest.sample.Bar
    x: abc
    y:
        one:
            :: libtest.sample.Foo
            username: aaa
            password: bbb
""")
    assert isinstance(c['a'], libtest.sample.Bar)
    assert c['a'].x == "abc"
    assert isinstance(c['a'].y, dict)
    assert isinstance(c['a'].y['one'], libtest.sample.Foo)
    assert c['a'].y['one'].creds == "aaa:bbb"
    assert c['a'].z == "defvalue"

def test_undefined_service(c):
    c.load_yaml("""
a: <wibble>
""")
    with raises(ValueError) as e:
        c['fred']
    assert "Undefined service 'fred'" in str(e.value)
    with raises(ValueError) as e:
        c['a']
    assert "Undefined service 'wibble'" in str(e.value)

def test_undefined_module_or_attribute(c):
    c.load_yaml("""
a:
    :: BLAH.UNDEFINED
b:
    :: libtest.UNDEFINED
""")
    with raises(AttributeError) as e:
        c['a']
    assert "'BLAH'" in str(e.value)
    with raises(AttributeError) as e:
        c['b']
    assert "'UNDEFINED'" in str(e.value)

def test_error_in_factory(c):
    c.load_yaml("""
a:
    :: libtest.sample.Foo.bad_factory
""")
    with raises(RuntimeError) as e:
        c['a']
    assert "Bleurgh" in str(e.value)
    assert "While calling factory 'libtest.sample.Foo.bad_factory'" in str(e.value)

def test_recursion_loop(c):
    c.load_yaml("""
a: <b>
b: <a>
""")
    with raises(ValueError) as e:
        c['a']
    assert "Loop detected" in str(e.value)

def test_thread_safe_object_creation(c):
    """
    If two threads try to fetch the object at the same time,
    only one instance should be created.
    This also tests assigning an existing function as a service.
    """
    cin = Queue()
    cout = Queue()
    def test_factory(username, password):
        cout.put("ready")
        cin.get()
        res = libtest.sample.Foo(username, password)
        cout.put("done")
        return res

    c['test_factory'] = test_factory
    c.load_yaml("""
a:
    :: <test_factory>
    username: abc
    password: xyz
""")
    def run(q):
        q.put("starting")
        q.put(c['a'])
    q1 = Queue()
    t1 = Thread(target=run, kwargs={"q":q1})
    t1.start()
    assert cout.get(True, 2) == "ready"
    assert q1.get(True, 2) == "starting"
    # Now t1 is waiting inside factory method

    q2 = Queue()
    t2 = Thread(target=run, kwargs={"q":q2})
    t2.start()
    assert q2.get(True, 2) == "starting"

    cin.put("go")
    assert cout.get(True, 2) == "done"
    t1.join(2)
    t2.join(2)
    assert cout.empty()

    res1 = q1.get(True, 2)
    res2 = q2.get(True, 2)
    # This also implies that test_factory was only called once
    # because otherwise t2 would hang waiting on cin
    assert isinstance(res1, libtest.sample.Foo)
    assert res1 is res2

def test_dynamically_named_services(c):
    """
    Test the pattern where an object can be passed the container
    and can instantiate objects from the container by service name.
    Since the initial object may be created under the container lock,
    if you use the container within the constructor then the lock
    will be called recursively (breaks if you change RLock to Lock)
    """
    class Dynamic(object):
        def __init__(self, container):
            self.container = container
            self.foo = container['dynamic/username']
            self.bar = container['dynamic/password']

    c['pato/container'] = c
    c['dynamic/factory'] = Dynamic
    c.load_yaml("""
dynamic/object:
    :: <dynamic/factory>
    container: <pato/container>
dynamic/username: abc
dynamic/password: xyzzy
""")
    res = c['dynamic/object']
    assert res.foo == "abc"

def test_missing_required_file(c):
    with raises(IOError):
        c.load_yaml_file("NONEXISTENT")

def test_optional_file(c):
    c.load_yaml_file("NONEXISTENT", required=False)
    # assert nothing raised
