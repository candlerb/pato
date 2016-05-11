# -*- coding: utf-8 -*-
"""
SOAP11 test cases based on https://www.w3.org/TR/2000/NOTE-SOAP-20000508/
SOAP12 test cases based on https://www.w3.org/TR/2007/REC-soap12-part0-20070427/
"""

from __future__ import absolute_import, division, print_function, unicode_literals
from collections import OrderedDict
from pato.soap import SOAPReceiver, SOAP11_ENCODING_STYLE
from pytest import fixture, raises
import re

NS1 = {"Some-URI": "xyz"}
MSG1 = """
<SOAP-ENV:Envelope
  xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
  SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
   <SOAP-ENV:Body>
       <m:GetLastTradePrice xmlns:m="Some-URI">
           <symbol>DIS</symbol>
       </m:GetLastTradePrice>
   </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

NS2 = OrderedDict([
  ("http://mycompany.example.com/employees", "nsn"),
  ("http://travelcompany.example.org/reservation/travel", "nsp"),
  ("http://travelcompany.example.org/reservation/hotels", "nsq"),
])
MSG2 = """<?xml version='1.0' ?>
<env:Envelope xmlns:env="http://www.w3.org/2003/05/soap-envelope"> 
 <env:Header>
  <m:reservation xmlns:m="http://travelcompany.example.org/reservation" 
          env:role="http://www.w3.org/2003/05/soap-envelope/role/next"
           env:mustUnderstand="true">
   <m:reference>uuid:093a2da1-q345-739r-ba5d-pqff98fe8j7d</m:reference>
   <m:dateAndTime>2001-11-29T13:20:00.000-05:00</m:dateAndTime>
  </m:reservation>
  <n:passenger xmlns:n="http://mycompany.example.com/employees"
          env:role="http://www.w3.org/2003/05/soap-envelope/role/next"
           env:mustUnderstand="true">
   <n:name>Åke Jógvan Øyvind</n:name>
  </n:passenger>
 </env:Header>
 <env:Body>
  <p:itinerary
    xmlns:p="http://travelcompany.example.org/reservation/travel">
   <p:departure>
     <p:departing>New York</p:departing>
     <p:arriving>Los Angeles</p:arriving>
     <p:departureDate>2001-12-14</p:departureDate>
     <p:departureTime>late afternoon</p:departureTime>
     <p:seatPreference>aisle</p:seatPreference>
   </p:departure>
   <p:return>
     <p:departing>Los Angeles</p:departing>
     <p:arriving>New York</p:arriving>
     <p:departureDate>2001-12-20</p:departureDate>
     <p:departureTime>mid-morning</p:departureTime>
     <p:seatPreference/>
   </p:return>
  </p:itinerary>
  <q:lodging
   xmlns:q="http://travelcompany.example.org/reservation/hotels">
   <q:preference>none</q:preference>
  </q:lodging>
 </env:Body>
</env:Envelope>"""

def test_soap11_example1_2():
    def myapp(data):
        assert data["xyz:GetLastTradePrice"]["symbol"] == "DIS"
        return {
            "xyz:GetLastTradePriceResponse": {
                "Price": 34.5,
            }
        }
    handler = SOAPReceiver(myapp, namespaces=NS1)

    raw = handler(MSG1)
    assert re.match(r"""^
    \s* <env:Envelope\s+xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
    \s* <env:Body>
    \s* <xyz:GetLastTradePriceResponse\s+xmlns:xyz="Some-URI">
    \s* <Price>34.5</Price>
    \s* </xyz:GetLastTradePriceResponse>
    \s* </env:Body>
    \s* </env:Envelope>
    \s* $""", raw, re.VERBOSE)

def test_soap11_encoding_style():
    def myapp(data):
        assert data["xyz:GetLastTradePrice"]["symbol"] == "DIS"
        return {
            "xyz:GetLastTradePriceResponse": {
                "Price": 34.5,
            }
        }
    handler = SOAPReceiver(myapp, namespaces=NS1, reply_attrs={
                           "@env:encodingStyle": SOAP11_ENCODING_STYLE,
    })

    raw = handler(MSG1)
    assert re.match(r"""^
    \s* <env:Envelope\s+xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
    \s* <env:Body>
    \s* <xyz:GetLastTradePriceResponse
        \s+ xmlns:xyz="Some-URI"
        \s+ env:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"
    \s* >
    \s* <Price>34.5</Price>
    \s* </xyz:GetLastTradePriceResponse>
    \s* </env:Body>
    \s* </env:Envelope>
    \s* $""", raw, re.VERBOSE)

def test_soap11_return_string():
    def myapp(data):
        return "foo<bar"
    handler = SOAPReceiver(myapp, namespaces=NS1)

    raw = handler(MSG1)
    assert re.match(r"""^
    \s* <env:Envelope\s+xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"\s+xmlns:xyz="Some-URI">
    \s* <env:Body>
    \s* foo&lt;bar
    \s* </env:Body>
    \s* </env:Envelope>
    \s* $""", raw, re.VERBOSE)

def test_soap11_return_none():
    def myapp(data):
        pass
    handler = SOAPReceiver(myapp, namespaces={"Some-URI": "xyz"})

    raw = handler(MSG1)
    assert re.match(r"""^
    \s* <env:Envelope\s+xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"\s+xmlns:xyz="Some-URI">
    \s* <env:Body>
    \s* </env:Body>
    \s* </env:Envelope>
    \s* $""", raw, re.VERBOSE)

def test_soap11_fault():
    def myapp(data):
        raise RuntimeError("Wibble")
    handler = SOAPReceiver(myapp, namespaces=NS1)
    raw = handler(MSG1)
    assert re.match(r"""^
    \s* <env:Envelope\s+xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
    \s* <env:Body>
    \s* <env:Fault>
    \s* <faultcode>env:Server</faultcode>
    \s* <faultstring>RuntimeError:\sWibble</faultstring>
    \s* <detail>.*File.*raise.*Wibble.*</detail>
    \s* </env:Fault>
    \s* </env:Body>
    \s* </env:Envelope>
    \s* $""", raw, re.VERBOSE|re.DOTALL)
                                        
def test_soap12_example1_2():
    def myapp(data):
        assert data["nsp:itinerary"]["nsp:departure"]["nsp:departing"] == "New York"
        return OrderedDict([
          ("nsp:itineraryClarification", OrderedDict([
            ("nsp:departure", {
              "nsp:departing": {
                "nsp:airportChoices": "JFK LGA EWR",
              },
            }),
            ("nsp:return", {
              "nsp:arriving": {
                "nsp:airportChoices": "JFK LGA EWR",
              },
            }),
          ])),
        ])
    handler = SOAPReceiver(myapp, namespaces=NS2)

    raw = handler(MSG2)
    assert re.match(r"""^
    \s* <env:Envelope\s+xmlns:env="http://www.w3.org/2003/05/soap-envelope">
    \s* <env:Body>
    \s* <nsp:itineraryClarification
        \s+ xmlns:nsn="http://mycompany.example.com/employees"
        \s+ xmlns:nsp="http://travelcompany.example.org/reservation/travel"
        \s+ xmlns:nsq="http://travelcompany.example.org/reservation/hotels"
    \s* >
    \s* <nsp:departure>
    \s* <nsp:departing>
    \s* <nsp:airportChoices>
    \s* JFK \s+ LGA \s+ EWR
    \s* </nsp:airportChoices>
    \s* </nsp:departing>
    \s* </nsp:departure>
    \s* <nsp:return>
    \s* <nsp:arriving>
    \s* <nsp:airportChoices>
    \s* JFK \s+ LGA \s+ EWR
    \s* </nsp:airportChoices>
    \s* </nsp:arriving>
    \s* </nsp:return>
    \s* </nsp:itineraryClarification>
    \s* </env:Body>
    \s* </env:Envelope>
    \s* $""", raw, re.VERBOSE)

def test_soap12_fault():
    def myapp(data):
        raise RuntimeError("Wibble")
    handler = SOAPReceiver(myapp, namespaces=NS2)
    raw = handler(MSG2)
    assert re.match(r"""^
    \s* <env:Envelope\s+xmlns:env="http://www.w3.org/2003/05/soap-envelope">
    \s* <env:Body>
    \s* <env:Fault>
    \s* <env:Code>
    \s* <env:Value>env:Receiver</env:Value>
    \s* </env:Code>
    \s* <env:Reason>
    \s* <env:Text>RuntimeError:\sWibble</env:Text>
    \s* </env:Reason>
    \s* <env:Detail>
    \s* <env:Text>.*File.*raise.*Wibble.*</env:Text>
    \s* </env:Detail>
    \s* </env:Fault>
    \s* </env:Body>
    \s* </env:Envelope>
    \s* $""", raw, re.VERBOSE|re.DOTALL)

def test_ctx():
    import pato.local
    def myapp(data):
        raise RuntimeError("Wibble")
    ctx = pato.local.local_factory()
    handler = SOAPReceiver(myapp, namespaces=NS1, ctx=ctx)
    raw = handler(MSG1)
    assert "Wibble" in raw
    assert ctx.error is True
    assert ctx.exc_info[0] is RuntimeError

def test_no_trap():
    def myapp(data):
        raise RuntimeError("Wibble")
    handler = SOAPReceiver(myapp, namespaces=NS1, trap_exception=False)
    with raises(RuntimeError) as e:
        handler(MSG1)
