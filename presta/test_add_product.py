import base64
import urllib
import urllib2

base64string = base64.encodestring('%s:' % 'CH0EVLRYYY9X6MIX2J4ZTWHZ65UG8WVI')[:-1]
authheader = "Basic %s" % base64string
xml = open('test.xml').read()
data = urllib.urlencode({'xml': xml})

req = urllib2.Request("http://%s/api/%s?XDEBUG_SESSION_START=1" % ('localhost:8080/prestashop', 'products'),
                              headers={'Content-Type': 'application/x-www-form-urlencoded',
                                       'Authorization': authheader})
result = urllib2.urlopen(req, data=data).read()

print result
