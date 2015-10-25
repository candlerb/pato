# Note: do not use unicode_literals because WSGI expects
# a "native string", which in python2.7 is b'....'
# See http://python-future.org/unicode_literals.html

class DBMiddleware(object):
    """
    A sample middleware for creating and closing a sqlalchemy session.
    This could be done more simply using pato.sqla.SessionManager
    """
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

class SimpleApp(object):
    def __call__(self, environ, start_response):
        res = environ['db'].execute('select count(*) from foo')
        start_response('200 OK', [('Content-Type:', 'text/plain')])
        return ['Result is ', repr(list(res))]
