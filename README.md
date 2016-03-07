# What is pato?

pato is a lightweight framework for building services in python.

pato services are plain python objects and therefore can be unit-tested
using whatever test framework you prefer.

pato allows you to connect services together easily, and you can create
multiple instances of the same service with different parameters (for
example, to connect to development and live backends)

pato is also [a yellow duck with big black eyes](http://pocoyoworld.wikia.com/wiki/Pato)

# pato.container

`pato.container` lets you create objects bound to service names, and for
objects to make use of other objects.  It is strongly based on
[this article](https://gist.github.com/blairanderson/8072d951a480a590f0bd)
from [Jim Weirich's](https://en.wikipedia.org/wiki/Jim_Weirich) blog in 2004.

You can think of it as a Service Locator with Dependency Injection.

`pato.container` is around 100 lines of code.

## Configuration

The container is normally initialised from a YAML file or files. Any definition
in a later file will override one given in an earlier file.

~~~
from pato.container import Container
c = Container()
c.load_yaml_file("base.yaml")
c.load_yaml_file("override.yaml", required=False)
~~~

Each YAML file is a dict (mapping) of service names to values.  In the simplest
case, a service can be just a plain value:

~~~
log_filename: /tmp/myapp.log
http_retries: 3
~~~

You access the values by indexing the container, e.g. `c['log_filename']` or
`c['http_retries']`

## Object creation

Where it starts to get interesting is that a dict value which contains the
special attribute `:` will call a factory function to create an object.  In
YAML, the syntax is `:: MODULE.FUNCTION_OR_CLASS`

~~~
database:
  :: sqlalchemy.create_engine
  name_or_url: sqlite:///test.db
  echo: True
~~~

Here this will dynamically load the module `sqlalchemy` and invoke `create_engine`
with the given keyword arguments `name_or_url` and `echo`.

Accessing `c['database']` will return this object, hence the
**Service Locator** pattern.

If you need to pass a list of unnamed arguments, pass a list for the `::` key.
This can be combined with keyword arguments if you wish as well.

~~~
database:
  :: [sqlalchemy.create_engine, "sqlite:///test.db"]
  echo: True
~~~

or:

~~~
database:
  ::
    - sqlalchemy.create_engine
    - sqlite:///test.db
  echo: True
~~~

## Dependency injection

What makes it *really* interesting is that you can pass other service
objects to the factory using the service name in angle-brackets, for
example:

~~~
crm:
  :: myapp.CRM
  db: <database>
  logger: <logger/sql>
logger/sql:
  :: myapp.SQLLogger
  database: <database>
~~~

(If you want to pass a string value which begins with `<` then double it to `<<`)

Dependencies are handled automatically, so that when you access `c['crm']`
then the `database` and `logger/sql` services will be created first (if not
already created) and passed to the crm constructor.

This feature also allows you to alias objects:

~~~
database/live:
  ...
database/dev:
  ...
database: <database/live>
~~~

and if you wish, you can give top-level placeholder names to configuration
values:

~~~
salesforce:
  :: simple_salesforce.Salesforce
  username: <config/salesforce/username>
  password: <config/salesforce/password>
  security_token: <config/salesforce/token>
  sandbox: <config/salesforce/sandbox>

config/salesforce/username: me@example.com
config/salesforce/password: xyzzy
config/salesforce/security_token: abcd1234
config/salesforce/sandbox: True
~~~

## Object lifecycle

Objects are created the first time that `c[servicename]` is called.
Subsequent calls will return the same object.

If you want to create all objects up-front then call `c.resolve_all()` after
loading the service definitions.  This can be helpful to make startup times
more deterministic and to catch errors earlier - although it may create
objects that your application never needs to use.

You can also add objects directly to the container by assigning their
object definition:

~~~
def my_function(username, password):
    ...

c = Container()
c['my_function'] = my_function
~~~

Once you have retrieved an object from the container, you use it as normal.
Typically it would be either an instance of a class or a callable.

~~~
print("Welcome to %s" % c['application_name'])
c['customer'].get(123)
c['logger']('hello')
~~~

Whether the object is thread-safe (or even needs to be) is entirely up to
your application.  However `pato.container` does ensure that only one instance
of each service is created, even if two threads try to instantiate it at the
same time.

## Service naming

You can structure your service names however you like.  The only requirement
is that they be unique within a given container.

It makes sense to create a logical hierarchy, for example so that all
services which provide the same external API (and are therefore
interchangeable) have the same prefix.

~~~
logger/console:
  ...

logger/sql:
  ...

logger/redis:
  ...
~~~

You can use dots as the separator if you wish, although that might be
confused with python packages.

## Accessing the container within factory functions

In some cases you might want the factory function to have access to the
entire container, so that it can access all available services by name.  To
do this, simply expose the container itself as a named service.

~~~
=== myapp.py
class Dynamic(object):
    def __init__(self, container):
        self.foo = container['dynamic/username']
        self.bar = container['dynamic/password']

=== myconf.yaml
dynamic/object:
  :: myapp.Dynamic
  container: <pato/container>
dynamic/username: abc
dynamic/password: xyzzy

=== main code
c = Container()
c['pato/container'] = c
c.load_yaml_file('myconf.yaml')
~~~

This approach can end up being more fragile if the factory method has
hard-coded names of services (as in the example above), but sometimes you do
want the factory to select services dynamically at runtime.

# Accessing request context

If a service needs to access the request context (e.g. for metadata about
where the request came from, or to access a shared database transaction)
then there are basically two main approaches:

* explicitly pass the request context from service to service
* use thread local variables. This functionality is built-in to python
  with `threading.local()` or see class Local in `werkzeug.local`

A context manager is provided in `pato.local` to set local attributes during
execution of a piece of code and remove them afterwards.
