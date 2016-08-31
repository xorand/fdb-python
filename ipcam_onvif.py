#!/usr/bin/env python

from argparse import ArgumentParser
from onvif import ONVIFService

# main program
parser = ArgumentParser(description='script for get ip camera info by onvif protocol')
parser.add_argument('--ip', action='store', default='', help='ip for search', required=True)
args = parser.parse_args()

try:
    device_service = ONVIFService('http://' + args.ip + '/onvif/device_service', 'Admin', '1234', '/usr/local/wsdl/devicemgmt.wsdl')
    ret = device_service.GetDeviceInformation()
except:
    device_service = ONVIFService('http://' + args.ip + '/onvif/device_service', 'admin', '12345', '/usr/local/wsdl/devicemgmt.wsdl')
    ret = device_service.GetDeviceInformation()

print 'Model:\t' + ret.Model
print 'S/N:\t' + ret.SerialNumber
ret = device_service.GetNetworkInterfaces()
print 'MAC:\t' + ret[0].Info['HwAddress'].upper()
