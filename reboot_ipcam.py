#!/usr/bin/python
from argparse import ArgumentParser
import httplib
import base64

# main program
parser = ArgumentParser(description='script for reboot ip camera by ip')
parser.add_argument('--ip', action='store', default='', help='camera ip address', required=True)
parser.add_argument('--model', action='store', default='evidence', choices=['evidence', 'hikvision'], help='ip camera model: evidence,hikvision')

args = parser.parse_args()
if args.model == 'evidence':
    url = '/cgi-bin/admin/restart.cgi'
    client = httplib.HTTPConnection(args.ip)
    headers = dict()
    headers["Authorization"] = "Basic " + base64.encodestring('%s:%s' % ('Admin', '1234'))[:-1]
    client.request('GET', url, None, headers)
    response = client.getresponse()
    if response.status != 200:
        print args.ip+' reboot failed (status '+str(response.status)+')'
    else:
        print args.ip+' rebooted'
