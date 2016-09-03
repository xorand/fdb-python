#!/usr/bin/python
import MySQLdb
from netaddr import EUI
from argparse import ArgumentParser

# main program
parser = ArgumentParser(description='summary report for ipcam from racktables db')
parser.add_argument('--query', type=str, default='ipc', help='query string')
parser.add_argument('--html', action='store_true', help='view report in html (default text)')
args = parser.parse_args()

db = MySQLdb.connect(host='localhost', user='root', passwd='ujhbkrj7', db='racktables_db', charset='utf8')
sql = 'select AttributeValue.string_value,Object.id,Object.name from AttributeValue \
left join Object on Object.id=AttributeValue.object_id where attr_id=3 and name like "%{}%"'.format(args.query)
cursor = db.cursor()
cursor.execute(sql)
data = cursor.fetchall()
if args.html:
    print '<table border=1><th>{}</th><th>{}</th><th>{}</th><th>{}</th><th>{}</th><th>{}</th><th>{}</th>'.format('name', 'ip', 'model', 'mac', 'uplink', 'uip', 'port')
else:
    print '{:11}{:15}{:32}{:18}{:15}{:16}{}'.format('name', 'ip', 'model', 'mac', 'uplink', 'uip', 'port')
for rec in data:
    obj_ip, obj_id, obj_name = rec
    sql = 'select AM.attr_id, D.dict_value, O.id as object_id from Object as O \
    left join AttributeMap as AM on O.objtype_id = AM.objtype_id \
    left join AttributeValue as AV on AV.attr_id = AM.attr_id and AV.object_id = O.id \
    left join Dictionary as D on D.dict_key = AV.uint_value and AM.chapter_id = D.chapter_id \
    where AM.attr_id=2 and object_id = '+str(obj_id)
    cur = db.cursor()
    cur.execute(sql)
    dt = cur.fetchall()
    for rc in dt:
        obj_attr_id, obj_hw, obj_id = rc
    obj_hw = obj_hw.replace('%GPASS%', ' ')
    sql = 'select Port.id, Port.l2address from Port where object_id = '+str(obj_id)
    cur = db.cursor()
    cur.execute(sql)
    dt = cur.fetchall()
    for rc in dt:
        obj_port_id, obj_mac = rc
    sql = 'select Object.name, Port.name, AttributeValue.string_value from Link \
        left join Port on porta=Port.id \
        left join Object on Port.object_id=Object.id \
        left join AttributeValue on Object.id=AttributeValue.object_id\
        where AttributeValue.attr_id=3 and portb='+str(obj_port_id)
    cur = db.cursor()
    cur.execute(sql)
    dt = cur.fetchall()
    for rc in dt:
        obj_up, obj_up_port, obj_up_ip = rc
        if args.html:
            print '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(obj_name, obj_ip, obj_hw, EUI(obj_mac), obj_up, obj_up_ip, obj_up_port)
        else:
            print '{:11}{:15}{:32}{:18}{:15}{:16}{}'.format(obj_name, obj_ip, obj_hw, EUI(obj_mac), obj_up, obj_up_ip, obj_up_port)
if args.html:
    print '</table>'
db.close()
