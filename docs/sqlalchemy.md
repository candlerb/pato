Using pato with sqlalchemy
==========================

If you are using the sqlalchemy ORM, every database operation has to take
place in the context of a [session](http://docs.sqlalchemy.org/en/rel_1_0/orm/session_basics.html).
A transaction occurs within a session, as does the maintenance of object state.

So it's a question of [how and when you create sessions](http://docs.sqlalchemy.org/en/rel_1_0/orm/session_basics.html#session-faq-whentocreate) -
and if you want to make multiple services do work within the same database transaction,
how you make the same session available to all of them when they execute, and commit
only once at the end.

Session argument
----------------

The most direct approach is to create a session when you need it (e.g. when
processing an incoming request) and to pass it around as a function argument.

The sqlalchemy `sessionmaker` function can create a session for you.

~~~
db/engine:
  :: [pato.sqla.create_engine, "sqlite:///test.db"]
  echo: True

db/session_factory:
  :: sqlalchemy.orm.sessionmaker
  bind: <db/engine>

myapp/foo:
  :: myapp.Foo
  other_service: ...
~~~

Example service code:

~~~
from contextlib import closing

class Foo(object):
    def __init__(self, other_service):
        self.other_service = other_service

    def baz(self, db, ...):
        ...
        ... do some work
        ...
        self.other_service(db, args)
        ...

### TOP-LEVEL CALLING CODE ###
foo = c['myapp/foo']
with closing(self.session_factory()) as db:
     foo.baz(db, ...)
     db.commit()
~~~

The 'closing' context manager ensures that the session is closed, even if an
exception takes place.  Closing a session implicitly rolls it back if it hasn't
committed.

Pros:

* The intent is clear: a function which takes a db session argument is likely to
  access the database
* The flow of data is obvious
* Every request has it's own fresh database session. In particular: if
  multiple requests are being handled in separate threads concurrently, each
  request will be using its own session.

Cons:

* The ultimate caller has to create a session and commit it
* Every service you call which uses or *might use* the database has to take
  a db argument.
    * If service A calls service B which calls service C, and service C uses
      the database, then service B must take a db argument and pass it through,
      even if B itself does not use the database
    * Let's say you have two versions of a service object: for example, a CRM
      which talks to Salesforce, and a mock CRM which uses a local mysql backend.
      If you want these objects to be plug-interchangable then they both have to
      take a database session argument - even though the Salesforce version doesn't
      need it.
* If you want to use services directly (e.g. for testing from the python
  shell) then you have to create the session, pass it as an argument, and
  commit explicitly.  This can become tedious:

    ~~~
    >>> service = c['other/service']
    >>> db = c['db/session_factory']()
    >>> service(db, ...)
    >>> db.commit()
    >>> db.close()
    ~~~

Context argument
----------------

The above approach can be made a little cleaner if instead of passing a
session argument, you pass an opaque "context" argument which may contain
the database session and any other information which may need to be shared
between services handling a particular request.

~~~
from bunch import Bunch
from contextlib import closing

class Foo(object):
    def __init__(self, other_service)
        self.other_service = other_service

    def baz(self, ctx, ...):
        ...
        ctx.db.add(...)
        ...
        self.other_service(ctx, args)
        ...

### TOP-LEVEL CALLING CODE ###
foo = c['myapp/foo']
with closing(self.session_factory()) as db:
     foo.baz(Bunch(db=db), ...)
     db.commit()
~~~

In turn `other_service` will pass on ctx to every other service it calls.

Pros:

* Passing an opaque "ctx" means that services which don't care about the database
  can ignore it
* Additional request-related information can be passed: for example, metadata about the
  IP address of the client which triggered the outer request.

Cons:

* All services have to take an initial ctx argument
* All services have to agree on the attribute names used for the information in ctx
* You need the top-level caller to create the ctx and the database session, and commit it
* Lower-level services may *add* information to the ctx, but should not create a fresh one
* Exercising services at the shell becomes even more tedious as you have to
  construct a suitable ctx (although you could have a helper function to do this)

    ~~~
    foo = c['myapp/foo']
    db = c['db/session_factory]()
    ctx = Bunch(db=db)
    foo.baz(ctx, ...)
    db.commit()
    db.close()
    ~~~

Existing context
----------------

There may be some existing object which you are passing around anyway:
in the case of WSGI this would be the environ argument.  In that case,
you can simply attach the db as an attribute to this object.

Unfortunately, WSGI `environ` is a dict not a user object, and can't have
attributes applied.  But it can have items inserted.

~~~
class SimpleApp(object):
    def __call__(self, environ, start_response):
        res = environ['db'].execute('select count(*) from foo')
        start_response('200 OK', [('Content-Type:', 'text/plain')])
        return ['Result is ', repr(list(res))]
~~~

The caller is responsible for setting this attribute. For WSGI
this can be done in some middleware.

~~~
class DBMiddleware(object):
    def __init__(self, session_factory, app):
        self.session_factory = session_factory
        self.app = app

    def __call__(self, environ, start_response):
        environ['db'] = self.session_factory()
        try:
            res = self.app(environ, start_response)
            environ['db'].commit()
            return res
        finally:
            environ['db'].close()
            del environ['db']
~~~

> If `environ` were a regular object, you could use the context manager
> `pato.local.setattrs` to add attributes and remove them afterwards.

Pros:

* You are passing around this object anyway

Cons:

* Care not to collide with an attribute of the same name
* You may need to copy attributes; e.g. the input part of your application
  may be using WSGI, but the body may be calling other functions which don't
  take the WSGI `environ` argument

Shared context
--------------

To avoid passing around a context explicitly, you can create a global
context object which all the services have access to, and insert a database
session within that.

There could be a problem if you are processing multiple requests
simultaneously in threads, as each thread requires its own database session
to work in.  However the standard python library provides a suitable
container in `threading.local()`, which ensures that each thread sees its
own independent values (even though it is the same container object).

There is a more comprehensive implementation in
[werkzeug.local.Local()](https://github.com/mitsuhiko/werkzeug/blob/master/docs/local.rst)
which is also able to keep separate state for greenlets.

A helper function `pato.local.local_factory` will use whichever is
available, and since you probably want the same context object everywhere, a
singleton is provided as `pato.local.ctx`.

> Flask's `request` object serves the same purpose and works in a similar
> way

Now the application configuration is straightforward:

~~
myapp/foo:
  :: myapp.Foo
  other_service: <myapp/bar>

myapp/bar:
  :: myapp.Bar
~~

and you don't need to pass around the context from call to call:

~~~
from pato.local import ctx

class Foo(object):
    def __init__(self, other_service)
        self.other_service = other_service

    def baz(self, ...):
        ...
        ctx.db.add(...)
        ...
        self.other_service(args)
        ...

class Bar(object):
    def __call__(self, args):
        ...
        ctx.db.add(...)
        ...
~~~

To invoke a service, it's still the responsibility of the top-level caller
to create a database session in the context beforehand, and commit or
rollback the session afterwards.  There is a helper object
`pato.sqla.SessionManager` which will do this for you.

~~~
db/manager:
  :: pato.sqla.SessionManager
  engine: <db/engine>
~~~

Then:

~~~
manager = c['db/manager']
foo = c['myapp/foo']
bar = c['myapp/bar']

# Calling one or more services within the same session/transaction.
# It sets ctx.db at the start and commits and removes at the end.
with manager():
    foo.baz(...)
    bar(...)

# Short form for calling a single service in a single session/transaction
manager.invoke(foo.baz, ...)
~~~

A compatible `TestSessionManager` is provided for use in test suites;
the transaction is always rolled back to clean up after each test.

Pros:
* No need to pass around a database session or context argument
* Still have a clear location where the sessions are constructed and destroyed
* The manager takes care of commit and rollback
* Works with or without associated HTTP requests
* Relatively straightforward: `pato.sqla.SessionManager` is only a few lines
  of self-contained code

Cons:
* Thread-local magic is going on in the background
* A little verbose to use from the shell:

   ~~~
   manager = c['db/manager']
   foo = c['myapp/foo']
   manager.invoke(foo.baz, ...)   # will create session and commit afterwards
   ~~~

* Tests need to ensure that a database session is inserted into the
  local object, and ideally removed afterwards.
* If you are using the SessionManager then you have to ensure that the `local`
  object passed to that is the same one as used by all your services.

Aside: the manager object can be used for creating and closing sessions,
even if you are not using a shared context and are explicitly passing the
session around.

~~~
manager = c['db/manager']

# one way
with manager() as db:
    other_func(db, ...)

# another way: sets 'db' attribute on the given object
arg = Bunch()
with manager(arg):
    other_func(arg, ...)
~~~

Scoped session
--------------

Sqlalchemy's [scoped session](http://docs.sqlalchemy.org/en/rel_1_0/orm/contextual.html)
gives an alternative and even more magic way to deal with this.

A 'scoped session' is a proxy object which stores a registry of sessions,
one associated to each thread.  If the current thread doesn't have a
session, a new one is created automatically.  All subsequent requests from
the same thread will receive the same session.

The session can be discarded using `session.remove()`, and then a subsequent request
from the same thread will get a fresh session.

~~~
db/engine:
  :: [pato.sqla.create_engine, "sqlite:///test.db"]
  echo: True

db/session_factory:
  :: sqlalchemy.orm.sessionmaker
  bind: <db/engine>

db/session:
  :: sqlalchemy.orm.scoped_session
  session_factory: <db/session_factory>

myapp/foo:
  :: myapp.Foo
  session: <db/session>
  other_service: <myapp/bar>

myapp/bar:
  :: myapp.Bar
  session: <db/session>
~~~

Example service code:

~~~
from contextlib import closing

class Foo(object):
    def __init__(self, session, other_service)
        self.db = session
        self.other_service = other_service

    def baz(self, ...):
        ...
        self.db.add(...)
        ...
        self.other_service(args)
        ...

class Bar(object):
    def __init__(self, session)
        self.db = session

    def __call__(self, args):
        ...
        self.db.add(...)
        ...

### TOP-LEVEL CALLING CODE ###
service = c['myapp/foo']
db = c['db/session']
try:
    service.baz(...)
    db.commit()
except:
    db.rollback()
finally:
    db.close()
    db.remove()
~~~

This makes the services very simple, because they can all hold the same
scoped session object, and it will refer to the correct underlying session which
is created on-demand if required.

Pros:

* No need to pass around a db session; any service which needs it can use it
* Standard sqlalchemy feature
* It's the mechanism which flask-sqlalchemy builds on
* Very easy to use services from the shell, since the db session is created as soon as
  it is needed

    ~~~
    foo = c['myapp/foo']
    foo.baz(...)

    # BUT DON'T FORGET!
    c['db/session'].commit()
    ~~~

* Easy to use ad-hoc database queries from the shell too

    ~~~
    db = c['db/session']
    db.execute("insert into foo (id) values (42)")
    db.commit()
    ~~~

Cons:

* Thread-local dynamic proxy object is perhaps too "magic" for your taste
* Although the ultimate caller does not need to create a session, they still have to
  commit it
* It is now critical that the caller close or rollback the session on exception,
  otherwise the session could be re-used with stale content
* It is safest for the caller also to remove the session, to force a fresh one to be
  created next time.

Usually it's obvious where to commit and remove the session - e.g.  at the
end of handling a HTTP request, or at the end of running a scheduled task. 
But if you call a service outside of those environments, you have to
remember to do the commit the session yourself.

Advanced session scoping
------------------------

You can also [bind the scoped_session](http://docs.sqlalchemy.org/en/rel_1_0/orm/contextual.html#using-custom-created-scopes)
to things other than the current thread.

~~~
try:
    from greenlet import getcurrent as get_ident
except ImportError:
    try:
        from thread import get_ident
    except ImportError:
        from _thread import get_ident

def greenlet_scoped_session(session_factory):
    return scoped_session(session_factory, scopefunc=get_ident)
~~~

If you are using a web framework like flask, it may already generate a
unique `request context` object while it is processing a HTTP request, and
you can bind the scoped_session to that.  This is what the flask-sqlalchemy
project does - it makes use of flask's `request` which is a
`werkzeug.local.LocalProxy` onto a `werkzeug.local.LocalStack` object.

Pros:

* Like `scoped_session`, but also supports greenlets (gunicorn) and other
  special scenarios
* Available already if you are using flask with flask-sqlalchemy

Cons:

* Even more magic
* You need to provide a function (scopefunc) which gives a unique
  indentifier for "the current request"
* Any service which uses this approach will fail if it tries to access the database outside
  of the context of a request
* Hence your [application testing](http://flask.pocoo.org/docs/0.10/testing/) must use helper
  functions to generate a mock request context

> Note 1: if you want to understand the implementation, look at
> [flask_sqlachemy](https://github.com/mitsuhiko/flask-sqlalchemy/blob/master/flask_sqlalchemy/__init__.py#L738),
> [flask.globals](https://github.com/mitsuhiko/flask/blob/master/flask/globals.py) and
> [werkzeug.local](https://github.com/mitsuhiko/werkzeug/blob/master/werkzeug/local.py)
> 
> Note 2: if using flask-sqlalchemy and the sqlalchemy ORM,
> [this note](https://github.com/mitsuhiko/flask-sqlalchemy/issues/98) shows
> how to make models which are also usable outside of flask.
> 
> Note 3: I found [this question](http://stackoverflow.com/questions/26555125/rollback-transactions-not-working-with-py-test-and-flask)
> useful when considering how to run a fast test suite which rolls back a database
> transaction rather than creating tables from scratch for every test.
