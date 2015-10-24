from __future__ import absolute_import, division, print_function, unicode_literals
import importlib, os, six, threading

def import_name(name):
    """
    Resolve a name like some.module.someclass.method
    """
    module = six.moves.builtins
    (modname, attrs) = (name, [])
    while modname:
        try:
            module = importlib.import_module(modname)
            break
        except ImportError:
            modname, _, nattr = modname.rpartition(".")
            attrs.insert(0, nattr)
    return reduce(getattr, attrs, module)

def raise_and_annotate(err, message):
    """
    When we get an exception resolving a service or calling a factory,
    this allows us to add additional information about what was being looked up.

    Based on idea from:
    http://stackoverflow.com/questions/9157210/how-do-i-raise-the-same-exception-with-a-custom-message-in-python
    """
    err.args = (err.args or ()) + (message,)
    raise

class Container(object):
    """
    A container which allows you to request a service by name.  A 'service' is
    just a Plain Old Python Object.  It could be as simple as a string:

    db_password: xyzzy

    or it could be an object constructed by a factory function:

    sql_engine:
        :: sqlalchemy.create_engine
        name_or_url: sqlite:///test.db
        echo: True

    One object can make use of other services by enclosing the service name
    in angle brackets.  Services can be defined in any order and pato will
    handle resolving them in the correct order.

    salesforce/dev:
        :: simple_salesforce.Salesforce
        username: me@example.com
        password: <salesforce/dev/password>
        security_token: xxxxxxxx
        sandbox: True

    customer/dev:
        :: myapp.Customer
        salesforce: <salesforce/dev>

    salesforce/dev/password: tcpip123

    customer: <customer/dev>

    Example Usage:

    c = Container()
    c.load_yamlfile('base.yaml')
    c.load_yamlfile('override.yaml')
    c.resolve_all()  # optional
    c['customer'].get(123)

    For more background to this approach see
    <https://gist.github.com/blairanderson/8072d951a480a590f0bd>
    """

    def __init__(self, factory_key=":", splat_key="="):
        self.definitions = {}    # {service name: configuration}
        self.services = {}       # {service name: constructed object}
        self.factory_key = factory_key
        self.splat_key = splat_key
        self.lock = threading.RLock()   # for thread-safety
        self.building = set()           # for loop detection

    def load_yaml_file(self, filename, required=True):
        """Import the named YAML file of service definitions"""
        try:
            with open(os.path.expanduser(filename)) as stream:
                self.load_yaml(stream)
        except IOError:
            if required:
                raise

    def load_yaml(self, stream):
        """Import a YAML string or stream of service definitions"""
        import yaml
        self.load_dict(yaml.load(stream))

    def load_dict(self, data):
        """Import a dict of {service: definition}"""
        self.definitions.update(data)
        for key in data:
            self.services.pop(key, None)

    def expire(self):
        """
        Force all services to be reloaded on next lookup
        (however, any object which has existing objects open
        will continue to use the old objects)
        """
        self.services.clear()

    def resolve_all(self):
        """
        Resolve all services 'eagerly'. Call this if you want to ensure your
        startup overhead is completed up-front, or to catch errors early
        before your server forks and runs.
        """
        for key in self.definitions:
            self.__getitem__(key)
        return self.services

    def __setitem__(self, name, definition):
        """
        Re-define a service. Does not affect existing objects, but future
        attempts to lookup this object will return a new instance.
        """
        self.definitions[name] = definition
        self.services.pop(name, None)

    def __delitem__(self, name):
        """
        Remove an object. Next retrieval from container will get a
        fresh object.
        """
        self.services.pop(name, None)

    def __contains__(self, name):
        """
        Returns true if the container has a given definition

        if "some/service" not in container: return
        """
        return name in self.definitions

    def __getitem__(self, name):
        """
        Return the service object corresponding to the given name, creating
        it dynamically if required
        """
        try:
            return self.services[name]
        except KeyError:
            with self.lock:
                self.building.clear()
                return self._resolve_service(name)

    def _resolve_service(self, name):
        if name in self.services:
            return self.services[name]
        if name not in self.definitions:
            raise ValueError("Undefined service '%s'" % name)
        if name in self.building:
            raise ValueError("Loop detected while resolving service '%s'" % name)
        self.building.add(name)
        try:
            self.services[name] = service = self._resolve_value(self.definitions[name])
        except Exception as err:
            raise_and_annotate(err, "While resolving service '%s'" % name)
        return service

    def _resolve_value(self, value):
        if isinstance(value, six.string_types):
            if value[0:2] == "<<":
                return value[1:]
            if value[0:1] == "<" and ">" in value:
                service_name, _, attrs = value[1:].rpartition(">")
                service = self._resolve_service(service_name)
                attrs = [a for a in attrs.split('.') if a]
                return reduce(getattr, attrs, service)

        elif isinstance(value, dict):
            if self.factory_key in value:
                factory = self._resolve_value(value[self.factory_key])
                if isinstance(factory, six.string_types):
                    factory = import_name(factory)
                args, kwargs = ([], {})
                for (dict_key, dict_value) in six.iteritems(value):
                    if dict_key == self.splat_key:
                        args = self._resolve_value(dict_value)
                        if not isinstance(args, list): args = [args]
                    elif dict_key != self.factory_key:
                        kwargs[dict_key] = self._resolve_value(dict_value)
                try:
                    return factory(*args, **kwargs)
                except Exception as err:
                    raise_and_annotate(err, "While calling factory '%s'" % value[self.factory_key])
            return {dict_key: self._resolve_value(dict_value)
                    for (dict_key, dict_value) in six.iteritems(value)}

        elif isinstance(value, list):
            return [self._resolve_value(item) for item in value]

        return value
