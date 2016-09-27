#!/usr/bin/env python

from argparse import ArgumentParser
from onvif import ONVIFService

# main program
parser = ArgumentParser(description='script for get ip camera info by onvif protocol')
parser.add_argument('--ip', action='store', default='', help='ip for search', required=True)
args = parser.parse_args()


def get_onvif_info(ip, login, password):
    wsdl_dev = '/usr/local/wsdl/devicemgmt.wsdl'
    wsdl_media = '/usr/local/wsdl/media.wsdl'
    url_dev = 'http://' + ip + '/onvif/device_service'

    # get device info and network interfaces
    try:
        srv_dev = ONVIFService(url_dev, login, password, wsdl_dev)
        dev_info = srv_dev.GetDeviceInformation()
        net_if = srv_dev.GetNetworkInterfaces()
    except:
        return(False, None, None, None, None)

    # get media service
    # if GetServices not supported - use same url as device service
    url_media = ''
    try:
        services = srv_dev.GetServices({'IncludeCapability': True})
        for srv in services:
            if str(srv.Namespace).lower().find('/media/') >= 0:
                url_media = str(srv.XAddr)
    except:
        url_media = url_dev

    try:
        srv_media = ONVIFService(url_media, login, password, wsdl_media)
    except:
        return(True, dev_info, net_if, '', '')

    # get profile1 token
    # if GetProfiles not supported - use 'Profile1'
    token = ''
    try:
        profiles = srv_media.GetProfiles()
        token = profiles[0]._token
    except:
        token = 'Profile1'
    try:
        stream_uri = srv_media.GetStreamUri({'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}}, 'ProfileToken': token}).Uri
        snapshot_uri = srv_media.GetSnapshotUri({'ProfileToken': token}).Uri
        return (True, dev_info, net_if, stream_uri, snapshot_uri)
    except:
        return(True, dev_info, net_if, '', '')

ret = False
if not ret:  # evidence
    (ret, dev_info, net_if, stream_uri, snapshot_uri) = get_onvif_info(args.ip, 'Admin', '1234')
if not ret:  # hikvision
    (ret, dev_info, net_if, stream_uri, snapshot_uri) = get_onvif_info(args.ip, 'admin', '12345')
if not ret:  # infinity
    (ret, dev_info, net_if, stream_uri, snapshot_uri) = get_onvif_info(args.ip, 'admin', 'admin')
if ret:
    print 'Vendor:\t' + dev_info.Manufacturer
    print 'Model:\t' + dev_info.Model
    print 'S/N:\t' + dev_info.SerialNumber
    print 'MAC:\t' + net_if[0].Info['HwAddress'].upper()
    print 'S1 URI:\t' + stream_uri
    print 'S1 SUR:\t' + snapshot_uri
