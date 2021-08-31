#!/usr/bin/env python3

from argparse import ArgumentParser
from pysnmp.entity.rfc3413.oneliner import cmdgen
import paramiko
import mysql.connector
from fdb_cfg import *


def fetch_fdb(ip, community):
    mib = '1.3.6.1.2.1.17.7.1.2.2.1.2'
    value = tuple([int(i) for i in mib.split('.')])
    generator = cmdgen.CommandGenerator()
    comm_data = cmdgen.CommunityData('server', community, 1)  # 1 means version SNMP v2c
    transport = cmdgen.UdpTransportTarget((ip, 161))

    real_fun = getattr(generator, 'nextCmd')
    (errorIndication, errorStatus, errorIndex, varBindTable) = real_fun(comm_data, transport, value)
    if errorIndication is not None or errorStatus is True:
        print('IP: %s Error: %s %s %s %s' % (ip, errorIndication, errorStatus, errorIndex, varBindTable))
    else:
        for varBindTableRow in varBindTable:
            # varBindTableRow:
            # [(ObjectName(1.3.6.1.2.1.17.7.1.2.2.1.2.5.0.27.144.212.92.45), Integer(27))]
            data = varBindTableRow[0][0][len(value):]
            vlan = data[0]
            mac = '%02X:%02X:%02X:%02X:%02X:%02X' % tuple(map(int, data[-6:]))
            port = varBindTableRow[0][1]
            yield {'vlan': vlan, 'mac': mac, 'port': port}


def ip2mac(ip, rt):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=rt, username=rt_login, password=rt_pass, port=rt_port, allow_agent=False, look_for_keys=False)

    # ping ip addres to populate arp table
    stdin, stdout, stderr = client.exec_command('ping count=1 '+ip)
    stdout.read()
    stdin, stdout, stderr = client.exec_command(':put [/ip arp get value-name=mac-address \
                                                [find where address={}]]'.format(ip))
    mac = stdout.read()[:17].decode('UTF-8')
    client.close()
    try:
        if mac[2] != ':':
            return ''
        else:
            return mac
    except:
        return ''


def mac2ip(mac, rt):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=rt, username=rt_login, password=rt_pass, port=rt_port, allow_agent=False, look_for_keys=False)

    stdin, stdout, stderr = client.exec_command('/ip arp print detail where mac-address={}'.format(mac.upper()))
    output = stdout.read().decode('UTF-8')
    ip_s = output.find('address=')
    ip_e = output.find('mac-address=')
    if ip_s > 0:
        ip = output[ip_s + 8:ip_e - 1]
    else:
        ip = ''
    client.close()
    return ip


def search_fdb_online(rt, switches):
    mac = ip2mac(args.ip, rt)
    if mac == '':
        return
    print(mac)
    for (sw, trunks) in switches:
        fdb = fetch_fdb(sw, 'public')
        for fdb_rec in fdb:
            if fdb_rec['mac'].upper() == mac.upper():
                if fdb_rec['port'] not in trunks or args.all:
                    print('sw: {} port: {}'.format(sw, fdb_rec['port']))


def check_trunk(ip, port, switches):
    trunk = False
    for (sw, trunks) in switches:
        if sw == ip and port in trunks:
            trunk = True
    return trunk


def ip2name(ip):
    cursor = db.cursor(buffered=True)
    cursor.execute('select Object.name from AttributeValue left join Object on Object.id=AttributeValue.object_id \
                   where attr_id=3 and AttributeValue.string_value=%s', (ip,))
    name = ''
    for (value,) in cursor:
        name = value
    return name


def search_fdb_cache():
    mac = ip2mac(args.ip, rt_n)
    if mac == '':
        mac = ip2mac(args.ip, rt_i)
    if mac == '':
        return
    print(mac)
    cursor = db.cursor(buffered=True)
    cursor.execute('select INET_NTOA(ip),port from FDB where l2address=%s', (mac.replace(':', ''),))
    for (ip, port) in cursor:
        trunk = False
        if not args.all:
            trunk = check_trunk(ip, port, sw_n) or check_trunk(ip, port, sw_i)
        if not trunk:
            if args.name:
                print('sw: {} ({}) port: {}'.format(ip, ip2name(ip), port))
            else:
                print('sw: {} port: {}'.format(ip, port))
    cursor.close()


def make_cache(switches):
    for (sw, trunks) in switches:
        print(sw)
        fdb = fetch_fdb(sw, 'public')
        for fdb_rec in fdb:
            mac = fdb_rec['mac'].replace(':', '')
            port = fdb_rec['port']
            cursor = db.cursor()
            cursor.execute('insert into FDB(ip,port,l2address) values (INET_ATON(%s),%s,%s)', (sw, str(port), mac))
            db.commit()
        print(' ... done')

# main program
parser = ArgumentParser(description='script for switches base fdb search')
parser.add_argument('--all', action='store_true', help='search all ports (by defaults ignore trunks)')
parser.add_argument('--name', action='store_true', help='print name of sw from racktables (work in search-cache mode only)')
parser.add_argument('--ip', action='store', default='', help='ip for search')
parser.add_argument('--mac', action='store', default='', help='mac for search')
parser.add_argument('--mode', action='store', default='search-online',
                    choices=['mac2ip', 'search-online', 'search-cache', 'make-cache'], help='script run mode')
args = parser.parse_args()

if args.mode == 'mac2ip':
    args.ip = mac2ip(args.mac, rt_n)
    if args.ip == '':
        args.ip = mac2ip(args.mac, rt_i)
    print('{} {}'.format(args.ip, args.mac))

if args.mode == 'search-online':
    if args.mac != '':
        args.ip = mac2ip(args.mac, rt_n)
        if args.ip == '':
            args.ip = mac2ip(args.mac, rt_i)
    if args.ip != '':
        print(args.ip)
        search_fdb_online(rt_n, sw_n)
        search_fdb_online(rt_i, sw_i)
else:
    db = mysql.connector.connect(user='root', password='ujhbkrj7', host='127.0.0.1', database='racktables_db')

if args.mode == 'make-cache':
    cursor = db.cursor()
    cursor.execute('delete from FDB')
    db.commit()
    make_cache(sw_n)
    make_cache(sw_i)
    db.close()
    print('all done')

if args.mode == 'search-cache':
    search_fdb_cache()
    db.close()
