#!/usr/bin/env python3

from argparse import ArgumentParser
import httplib2

# main program
parser = ArgumentParser(description='script for reboot ip camera by ip')
parser.add_argument('--ip', action='store', default='', help='camera ip address', required=True)
parser.add_argument('--model', action='store', default='evidence', choices=['evidence', 'hikvision'], help='ip camera model: evidence,hikvision')

args = parser.parse_args()
if args.model == 'evidence':
    url = '/cgi-bin/admin/restart.cgi'
    login = 'Admin'
    password = '1234'
    client = httplib2.Http()
    client.add_credentials(login, password)
    resp, content = client.request('http://' + args.ip + url, 'GET', headers={'content-type': 'text/plain'})
    if resp.status != 200:
        print(args.ip+' reboot failed (status '+str(resp.status)+')')
    else:
        print(args.ip+' rebooted')
