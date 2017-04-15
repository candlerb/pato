"""
Utilities for using pato with SQLAlchemy
"""

from __future__ import absolute_import, division, print_function, unicode_literals
from contextlib import contextmanager
from pato.local import get_ctx
from sqlalchemy import event, create_engine as real_create_engine
from sqlalchemy.orm import sessionmaker

SENTINEL = object()

def create_engine(*args, **kwargs):
    """
    Create an engine including workarounds for specific backends
    """
    engine = real_create_engine(*args, **kwargs)

    if engine.name == "sqlite":
        # http://docs.sqlalchemy.org/en/rel_1_0/dialects/sqlite.html#pysqlite-serializable
        @event.listens_for(engine, "connect")
        def do_connect(dbapi_connection, connection_record):
            # disable pysqlite's emitting of the BEGIN statement entirely.
            # also stops it from emitting COMMIT before any DDL.
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def do_begin(conn):
            # emit our own BEGIN
            conn.execute("BEGIN")

    return engine

class SessionManager(object):
    def __init__(self, engine, session_factory=None, ctx_factory=get_ctx, attribute_name="db"):
        self.engine = engine
        self.session_factory = session_factory or sessionmaker(bind=engine)
        self.ctx_factory = ctx_factory
        self.attribute_name = attribute_name

    @contextmanager
    def __call__(self, ctx=None, force_new=False):
        """
        A context manager which creates a database session. Afterwards it
        either commits or rolls back the session and closes it. The session
        value is yielded and also added to the ctx object for the
        duration of the call.

        If there is already a session in the ctx object then this is
        used instead of creating a new session, unless force_new is True.
        This allows recursive use.

        sessionmgr = SessionManager(engine)
        ...
        with sessionmgr() as session:
            ... do stuff with session
        """
        if not ctx: ctx = self.ctx_factory()
        old_session = getattr(ctx, self.attribute_name, SENTINEL)
        if old_session is not SENTINEL and old_session is not None and not force_new:
            yield old_session
        else:
            session = self.session_factory()
            setattr(ctx, self.attribute_name, session)
            try:
                yield session
                session.commit()
            except:
                session.rollback()
                raise
            finally:
                session.close()
                if old_session is SENTINEL:
                    delattr(ctx, self.attribute_name)
                else:
                    setattr(ctx, self.attribute_name, old_session)

    def invoke(self, service, *args, **kwargs):
        """
        Invoke a single function, ensuring that a database session has been
        created in the ctx object, and finishing up afterwards.

        sessionmgr = SessionManager(engine)
        ...
        sessionmgr.invoke(myservice, arg1, arg2)
        """
        with self():
            return service(*args, **kwargs)

class TestSessionManager(SessionManager):
    """
    A context manager for use in test suites. The session itself may
    do commits and rollbacks, but at the end everything is rolled back.

    sessionmgr = TestSessionManager(engine)
    ...
    @yield_fixture
    def session():
        with sessionmgr() as s:
            yield s
    """

    @contextmanager
    def __call__(self, ctx=None, force_new=False):
        """
        There is deep magic here to allow our session to commit/rollback
        inside a single transaction, which we can roll back at the very end. See
        http://docs.sqlalchemy.org/en/rel_1_1/orm/session_transaction.html#session-external-transaction
        and in particular the section "Supporting Tests with Rollbacks"
        """
        if not ctx: ctx = self.ctx_factory()
        old_session = getattr(ctx, self.attribute_name, SENTINEL)
        if old_session is not SENTINEL and old_session is not None and not force_new:
            yield old_session
        else:
            conn = self.engine.connect()
            trans = conn.begin()
            session = self.session_factory(bind=conn)
            session.begin_nested()
            @event.listens_for(session, "after_transaction_end")
            def restart_savepoint(session, transaction):
                if transaction.nested and not transaction._parent.nested:
                    session.expire_all()
                    session.begin_nested()
            setattr(ctx, self.attribute_name, session)
            try:
                yield session
            finally:
                session.close()
                trans.rollback()
                conn.close()
                if old_session is SENTINEL:
                    delattr(ctx, self.attribute_name)
                else:
                    setattr(ctx, self.attribute_name, old_session)
