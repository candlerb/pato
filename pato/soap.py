from __future__ import absolute_import, division, print_function, unicode_literals
from collections import OrderedDict  # for deterministic XML
from contextlib import contextmanager
import sys
from traceback import format_exception_only, format_tb
import xmltodict

SOAP11 = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP12 = "http://www.w3.org/2003/05/soap-envelope"

SOAP11_ENCODING_STYLE = "http://schemas.xmlsoap.org/soap/encoding/"
SOAP12_ENCODING_STYLE = "http://www.w3.org/2003/05/soap-encoding"

class SOAPReceiver(object):
    """
    Takes a text body, invokes the wrapped app function. It passes a
    single argument which is a dict containing the parsed XML
    (without SOAP envelope/header).

    The app return value should be a dict suitable for conversion to XML.
    It may also be a plain string or None, but those are unlikely to be
    useful as you won't get a top-level XML element inside the SOAP
    response.

    An exception is converted into a SOAP fault, unless you set
    trap_exception=False.
    """

    NAMESPACES = OrderedDict([
      (SOAP11, "s11"),
      (SOAP12, "s12"),
    ])

    def __init__(self, app, namespaces=None, reply_attrs=None,
                 unparse_options=dict(pretty=True, full_document=False, indent="  "),
                 encoding_style=None, trap_exception=True, ctx=None):
        self.app = app
        self.namespaces = namespaces
        self.reply_attrs = reply_attrs
        self.unparse_options = unparse_options
        self.encoding_style = encoding_style
        self.trap_exception = trap_exception
        self.ctx = ctx
        if namespaces:
            self.parse_ns = self.NAMESPACES.copy()
            self.parse_ns.update(namespaces)
        else:
            self.parse_ns = self.NAMESPACES

    def __call__(self, text):
        soap_version = None
        try:
            data = xmltodict.parse(text, process_namespaces=True,
                                   namespaces=self.parse_ns)
            if "s11:Envelope" in data:
                soap_version = SOAP11
                body = data["s11:Envelope"]["s11:Body"]
            elif "s12:Envelope" in data:
                soap_version = SOAP12
                body = data["s12:Envelope"]["s12:Body"]
            else:
                if self.ctx:
                    self.ctx.exc_info = None
                    self.ctx.error = True
                return "Missing SOAP Envelope"
            res = self.app(body)
            out = OrderedDict([
                ("env:Envelope", OrderedDict([
                    ("@xmlns:env", soap_version),
                    ("env:Body", res),
                ])),
            ])
            # Add namespace attributes, preferably to the inner top-level element
            # but fallback to putting them on the Envelope
            root = out["env:Envelope"]
            try:
                keys = res.keys()
                if len(keys) == 1:
                    root = res[keys[0]]
            except AttributeError:
                pass
            for (k, v) in self.namespaces.iteritems():
                root["@xmlns:"+v] = k
            # Add canned attributes, typically for adding encodingStyle
            # (Note: SOAP 1.1 allows this to be anywhere including on the
            # envelope, but SOAP 1.2 is more restrictive)
            if self.reply_attrs:
                root.update(self.reply_attrs)
            return xmltodict.unparse(out, **self.unparse_options)

        except Exception:
            if not self.trap_exception: raise
            exc_info = sys.exc_info()
            if self.ctx:
                # This allows the exception to be logged elsewhere,
                # and for a HTTP connector to return a 500 status code
                self.ctx.exc_info = exc_info
                self.ctx.error = True
            return xmltodict.unparse(self.fault(exc_info, soap_version),
                                     **self.unparse_options)

    def fault(self, exc_info, soap_version=None):
        reason = "".join(format_exception_only(*exc_info[0:2])).strip()
        detail = "".join(format_tb(*exc_info[2:])).strip()
        if soap_version == SOAP12:
            # https://www.w3.org/TR/2007/REC-soap12-part0-20070427/#L11549
            res = OrderedDict([
                ("env:Fault", OrderedDict([
                    ("env:Code", OrderedDict([
                        ("env:Value", "env:Receiver"),
                    ])),
                    ("env:Reason", OrderedDict([
                        ("env:Text", reason),
                    ])),
                    ("env:Detail", OrderedDict([
                        ("env:Text", detail),
                    ])),
                ])),
            ])
        else:
            # https://www.w3.org/TR/2000/NOTE-SOAP-20000508/
            res = OrderedDict([
                ("env:Fault", OrderedDict([
                    ("faultcode", "env:Server"),
                    ("faultstring", reason),
                    ("detail", detail),
                ])),
            ])
        return OrderedDict([
            ("env:Envelope", OrderedDict([
                ("@xmlns:env", soap_version or SOAP11),
                ("env:Body", res),
            ])),
        ])
