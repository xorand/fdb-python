#!/usr/bin/python
from argparse import ArgumentParser
from pysnmp.entity.rfc3413.oneliner import cmdgen
import paramiko

# (ip,(trunk_port1, ...))
sw_n = (
    ('192.168.100.100', (2, 9, 10, 11, 12, 13, 14, 15)),
    ('192.168.100.101', (26,)),
    ('192.168.100.102', (26,)),
    ('192.168.100.103', (26,)),
    ('192.168.100.104', (26,)),
    ('192.168.100.105', (48,)),
    ('192.168.100.106', (3, 5, 9, 10, 11, 12, 13, 14)),
    ('192.168.100.107', (25,)),
    ('192.168.100.108', (25,)),
    ('192.168.100.109', (25,)),
    ('192.168.100.110', (25,)),
    ('192.168.100.111', (25,)),
    ('192.168.100.112', (25,)),
    ('192.168.100.113', (28,)),
    ('192.168.100.114', (26,)),
    ('192.168.100.115', (26,)),
    ('192.168.100.116', ())
)

sw_i = (
    ('192.168.101.101', (25,)),
    ('192.168.101.102', (25,)),
    ('192.168.101.103', (50,)),
    ('192.168.101.104', (25,)),
    ('192.168.101.105', (25,)),
    ('192.168.101.106', (25,)),
    ('192.168.101.111', (1, 3, 4, 6, 8, 11))
)

rt_n = '192.168.1.200'
rt_i = '192.168.3.200'
rt_login = 'admin'
rt_pass = 'vtufgfccdjhl'
rt_port = 7772


def fetch_fdb(ip, community):
    mib = '1.3.6.1.2.1.17.7.1.2.2.1.2'
    value = tuple([int(i) for i in mib.split('.')])
    generator = cmdgen.CommandGenerator()
    comm_data = cmdgen.CommunityData('server', community, 1)  # 1 means version SNMP v2c
    transport = cmdgen.UdpTransportTarget((ip, 161))

    real_fun = getattr(generator, 'nextCmd')
    (errorIndication, errorStatus, errorIndex, varBindTable) = real_fun(comm_data, transport, value)
    if errorIndication is not None or errorStatus is True:
        print "IP: %s Error: %s %s %s %s" % (ip, errorIndication, errorStatus, errorIndex, varBindTable)
    else:
        for varBindTableRow in varBindTable:
            # varBindTableRow:
            # [(ObjectName(1.3.6.1.2.1.17.7.1.2.2.1.2.5.0.27.144.212.92.45), Integer(27))]
            data = varBindTableRow[0][0][len(value):]
            vlan = data[0]
            mac = '%02X:%02X:%02X:%02X:%02X:%02X' % tuple(map(int, data[-6:]))
            port = varBindTableRow[0][1]
            yield {'vlan': vlan, 'mac': mac, 'port': port}


def search_fdb(rt, switches):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=rt, username=rt_login, password=rt_pass, port=rt_port, allow_agent=False, look_for_keys=False)

    # ping ip addres to populate arp table
    stdin, stdout, stderr = client.exec_command('ping count=1 '+args.ip)
    stdout.read()
    stdin, stdout, stderr = client.exec_command(':put [/ip arp get value-name=mac-address [find where address={}]]'.format(args.ip))
    mac = stdout.read()[:17]
    client.close()
    try:
        if mac[2] != ':':
            return
    except:
        return
    print mac
    for (sw, trunks) in switches:
        fdb = fetch_fdb(sw, 'public')
        for fdb_rec in fdb:
            if fdb_rec['mac'].upper() == mac.upper():
                if fdb_rec['port'] not in trunks or args.all:
                    print 'sw: {} port: {}'.format(sw, fdb_rec['port'])

# main program
parser = ArgumentParser(description='script for switches base fdb search')
parser.add_argument('--all', action='store_true', help='search all ports (by defaults ignore trunks)')
parser.add_argument('--ip', action='store', default='', help='ip for search', required=True)

args = parser.parse_args()

search_fdb(rt_n, sw_n)
search_fdb(rt_i, sw_i)
