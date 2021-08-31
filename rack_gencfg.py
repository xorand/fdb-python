#!/usr/bin/env python3
import mysql.connector
import yaml
import sys

if len(sys.argv) < 2:
    sys.exit(0)
obj_id = sys.argv[1]

db = mysql.connector.connect(host='localhost', user='racktables_user', passwd='ujhbkrj7', db='racktables_db', charset='utf8')
cursor = db.cursor()
config = {}
sql = "SELECT ansible_extra_vars FROM AnsibleExtra WHERE object_id = {}".format(obj_id)
cursor.execute(sql)
result = cursor.fetchall()
try:
    extra_conf = result[0][0]
except:
    extra_conf = ""
if extra_conf != "":
    config = yaml.safe_load(extra_conf)

sql = "SELECT REPLACE(LEFT(D.dict_value, POSITION('%GPASS%' IN D.dict_value) - 1), '[', '') AS model FROM Object As O \
    LEFT JOIN AttributeMap AS AM ON O.objtype_id = AM.objtype_id \
    LEFT JOIN AttributeValue AS AV ON AV.attr_id = AM.attr_id and AV.object_id = O.id \
    LEFT JOIN Dictionary AS D ON D.dict_key = AV.uint_value AND AM.chapter_id = D.chapter_id \
    WHERE AM.attr_id=2 AND object_id={}".format(obj_id)
cursor.execute(sql)
result = cursor.fetchall()
try:
    model = result[0][0]
except:
    model = ""

if model == 'MikroTik' and extra_conf.find('bridge_vlan') != -1:
    model = 'MikroTikHWVlan'

sql = "SELECT PortAllowedVLAN.vlan_id, VLANDescription.vlan_descr FROM PortAllowedVLAN LEFT JOIN VLANDescription ON \
    PortAllowedVLAN.vlan_id = VLANDescription.vlan_id WHERE object_id={} \
    GROUP BY PortAllowedVLAN.vlan_id, VLANDescription.vlan_descr".format(obj_id)
cursor.execute(sql)
vlans = cursor.fetchall()
for vlan in vlans:
    if model == 'MikroTik':
        config.setdefault("ros_bridges", []).append('bridge-' + vlan[1])
    else:
        config.setdefault("vlans", []).append({'name': vlan[1], 'tag': vlan[0]})

if model == 'MikroTik':
    sql = "SELECT Port.name, PortVLANMode.vlan_mode FROM Port LEFT JOIN PortVLANMode on Port.name = PortVLANMode.port_name \
        AND Port.object_id = PortVLANMode.object_id WHERE Port.object_id = {} AND LENGTH(PortVLANMode.vlan_mode) > 0 \
        ORDER BY LENGTH(Port.name), Port.name".format(obj_id)
elif model == 'MikroTikHWVlan':
    sql = "SELECT Port.name, PortVLANMode.vlan_mode FROM Port LEFT JOIN PortVLANMode on Port.name = PortVLANMode.port_name \
        AND Port.object_id = PortVLANMode.object_id WHERE Port.object_id = {} AND LENGTH(PortVLANMode.vlan_mode) > 0 \
        ORDER BY LENGTH(Port.name), Port.name".format(obj_id)
else:
    sql = "SELECT Port.name, PortVLANMode.vlan_mode FROM Port LEFT JOIN PortVLANMode on Port.name = PortVLANMode.port_name \
        AND Port.object_id = PortVLANMode.object_id WHERE Port.object_id = {} AND LENGTH(PortVLANMode.vlan_mode) > 0 \
        ORDER BY Port.id".format(obj_id)
cursor.execute(sql)
ports = cursor.fetchall()
for port in ports:
    sql_port = "SELECT PortAllowedVLAN.vlan_id, VLANDescription.vlan_descr FROM PortAllowedVLAN LEFT JOIN VLANDescription ON \
        PortAllowedVLAN.vlan_id = VLANDescription.vlan_id WHERE object_id={} AND port_name = '{}'".format(obj_id, port[0])
    cursor_port = db.cursor()
    cursor_port.execute(sql_port)
    port_vlans = cursor_port.fetchall()
    if model == 'MikroTik':
        config.setdefault("ros_bridge_ports", []).append({'port': port[0]})
        index = config.setdefault("ros_bridge_ports", []).index({'port': port[0]})
        if port[1] == 'trunk':
            config.setdefault("ros_bridge_ports", [])[index]['bridge'] = None
            if port_vlans != []:
                config.setdefault("ros_bridge_ports", [])[index]['vlan'] = []
            for port_vlan in port_vlans:
                config.setdefault("ros_bridge_ports", [])[index]['vlan'].append({'tag': port_vlan[0], 'bridge': 'bridge-' + port_vlan[1]})
        else:
            for port_vlan in port_vlans:
                config.setdefault("ros_bridge_ports", [])[index]['bridge'] = 'bridge-' + port_vlan[1]
    else:
        port_name = ""
        try:
            port_name = int(port[0])
        except:
            port_name = port[0]
        config.setdefault('ports', []).append({'name': port_name})
        index = config.setdefault("ports", []).index({'name': port_name})
        config.setdefault('ports', [])[index]['type'] = port[1]
        if port[1] == 'access':
            config.setdefault('ports', [])[index]['vlan'] = port_vlans[0][0]
        else:
            vlan_cfg = []
            for port_vlan in port_vlans:
                vlan_cfg.append(str(port_vlan[0]))
            config.setdefault('ports', [])[index]['vlan'] = ','.join(vlan_cfg)

sql = "SELECT Dictionary.dict_value FROM Object LEFT JOIN Dictionary ON \
    Dictionary.dict_key = Object.objtype_id WHERE Object.id = {} AND Dictionary.chapter_id = 1".format(obj_id)
cursor.execute(sql)
rack_type = cursor.fetchall()
config['rack_type'] = rack_type[0][0]


def represent_none(self, _):
    return self.represent_scalar('tag:yaml.org,2002:null', '')

yaml.add_representer(dict, lambda self, data: yaml.representer.SafeRepresenter.represent_dict(self, data.items()))
yaml.add_representer(type(None), represent_none)
config_yaml = yaml.dump(config, explicit_start=True, explicit_end=True, default_flow_style=False, default_style=None)
config_yaml = config_yaml.replace("'", "")
print(config_yaml)
db.close()
