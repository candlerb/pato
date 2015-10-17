from __future__ import absolute_import, division, print_function, unicode_literals
from pato.sqla import SessionManager, TestSessionManager
from pytest import raises

class AnyObject():
    pass

class MockSession:
    def __init__(self):
        self.calls = []
    def close(self, *args, **kwargs):
        self.calls.append(('close', args, kwargs))
    def commit(self, *args, **kwargs):
        self.calls.append(('commit', args, kwargs))
    def rollback(self, *args, **kwargs):
        self.calls.append(('rollback', args, kwargs))

def test_create_session_and_nesting():
    sm = SessionManager(engine=None, session_factory=MockSession)
    with sm() as s1:
        with sm() as s2:
            assert s2 is s1
        assert s1.calls == []
        with sm(force_new=True) as s3:
            assert s3 is not s1
            assert s3.calls == []
        assert s1.calls == []
        assert s3.calls == [
            ('commit', (), {}),
            ('close', (), {}),
        ]
    assert s1.calls == [
        ('commit', (), {}),
        ('close', (), {}),
    ]

def test_rollback():
    """
    With nested call to SessionManager, such that the inner
    call yields the same session, then only the outer one rolls back
    """
    sm = SessionManager(engine=None, session_factory=MockSession)
    with raises(RuntimeError):
        with sm() as s1:
            with raises(ValueError):
                with sm() as s2:
                    assert s2 is s1
                    raise ValueError("foo")
            assert s1.calls == []
            raise RuntimeError("bar")
    assert s1.calls == [
        ('rollback', (), {}),
        ('close', (), {}),
    ]

def test_arg():
    sm = SessionManager(engine=None, session_factory=MockSession)
    arg = AnyObject()
    with sm(arg) as s1:
        assert arg.db is s1
        with sm(arg) as s2:
            assert s2 is s1
            assert arg.db is s1
        assert arg.db is s1
    assert not hasattr(arg, 'db')
