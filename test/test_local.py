from __future__ import absolute_import, division, print_function, unicode_literals
from pato.local import setattrs, local_factory, ctx
from pytest import raises

class AnyObject(object):
    pass

def test_setattrs_local():
    foo = AnyObject()
    assert not hasattr(foo, 'a')
    assert not hasattr(foo, 'b')
    with setattrs(foo, a='hello', b='world'):
        assert foo.a == 'hello'
        assert foo.b == 'world'
    assert not hasattr(foo, 'a')
    assert not hasattr(foo, 'b')

def test_setattrs_nested():
    foo = local_factory()
    assert foo is not ctx
    assert not hasattr(foo, 'a')
    foo.b = 'grumpy'
    with setattrs(foo, a='hello', b='world'):
        assert foo.a == 'hello'
        assert foo.b == 'world'
        with setattrs(foo, a='goodbye'):
            assert foo.a == 'goodbye'
            assert foo.b == 'world'
        assert foo.a == 'hello'
        assert foo.b == 'world'
    assert not hasattr(foo, 'a')
    assert foo.b == 'grumpy'

def test_setattrs_ctx():
    """
    There is a shared ctx object which is the default target
    """
    assert not hasattr(ctx, 'a')
    assert not hasattr(ctx, 'b')
    with setattrs(a='hello', b='world'):
        assert ctx.a == 'hello'
        assert ctx.b == 'world'
        with setattrs(a='goodbye'):
            assert ctx.a == 'goodbye'
            assert ctx.b == 'world'
        assert ctx.a == 'hello'
        assert ctx.b == 'world'
    assert not hasattr(ctx, 'a')
    assert not hasattr(ctx, 'b')
