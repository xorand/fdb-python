#!/usr/bin/python
import MySQLdb
import rtapi
import sys

db = MySQLdb.connect(host='127.0.0.1', port=3306, passwd='ujhbkrj7', db='racktables_db', user='racktables_user')
rt = rtapi.RTObject(db)

rack_name = sys.argv[1]
rack_type = sys.argv[2].strip('"')
rack_ip = sys.argv[3]
rack_ports = int(sys.argv[4])
rack_hw_type = sys.argv[5].strip('"')
sp = rack_hw_type.find(' ')
rack_hw_type = rack_hw_type[:sp] + '%GPASS%' + rack_hw_type[sp + 1:]
rack_serial = sys.argv[6]

attr_id_fqdn = 3
attr_id_hwtype = 2
attr_id_backup = 10004
attr_value_backup_yes = 1501
interface_name = 'eth'

obj_id = rt.GetObjectId(rack_name)
obj_type_id = rt.GetDictionaryId(rack_type)
print(obj_type_id)
if obj_id is None:
    if rack_serial == '-':
        sql = "INSERT INTO Object (name, objtype_id) VALUES ('%s',%d)" % (rack_name, obj_type_id)
    else:
        sql = "INSERT INTO Object (name, objtype_id, asset_no) VALUES ('%s', %d, '%s')" % (rack_name, obj_type_id, rack_serial)
    rt.db_insert(sql)
    obj_id = rt.db_fetch_lastid()
else:
    if rack_serial != '-':
        sql = "UPDATE Object SET asset_no = '%s' WHERE id = %d" % (rack_serial, obj_id)
        rt.db_insert(sql)
rt.InsertOrUpdateAttribute(obj_id, attr_id_fqdn, rack_ip)
if rack_ports == 1:
    rt.UpdateNetworkInterface(obj_id, interface_name)
else:
    for num in range(rack_ports):
        rt.UpdateNetworkInterface(obj_id, 'ether{}'.format(str(num + 1)))
rt.InterfaceAddIpv4IP(obj_id, interface_name, rack_ip)
try:
    rt.InsertOrUpdateAttribute(obj_id, attr_id_backup, attr_value_backup_yes)
except:
    pass
if rack_hw_type != '-':
    print(rack_hw_type)
    obj_hw_id = rt.GetDictionaryId(rack_hw_type)
    print(obj_hw_id)
    if obj_hw_id is None:
        sql = "SELECT chapter_id FROM AttributeMap WHERE attr_id = {} AND objtype_id = {}".format(attr_id_hwtype, obj_type_id)
        chapter_id = rt.db_query_one(sql)[0]
        rt.InsertDictionaryValue(chapter_id, rack_hw_type)
    obj_hw_id = rt.GetDictionaryId(rack_hw_type)
    rt.InsertOrUpdateAttribute(obj_id, attr_id_hwtype, obj_hw_id)
sql = "DELETE FROM ObjectLog WHERE object_id={}".format(obj_id)
rt.db_insert(sql)
try:
    obj_parent_id = rt.GetObjectId(sys.argv[7])
    sql = "INSERT INTO EntityLink (parent_entity_type, parent_entity_id, child_entity_type, child_entity_id) VALUES ('object', {}, 'object', {})".format(obj_parent_id, obj_id)
    rt.db_insert(sql)
except:
    pass
sys.exit(0)
