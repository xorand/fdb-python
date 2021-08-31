#!/usr/bin/env python3
import mysql.connector
import json


def add_item(list, index, value):
    if list.get(index) == None:
        list[index] = [value]
    else:
        if value not in list[index]:
            list[index].append(value)

db = mysql.connector.connect(host='localhost', user='racktables_user', passwd='ujhbkrj7', db='racktables_db', charset='utf8')
sql = "SELECT Object.name AS name, INET_NTOA(IPv4Allocation.ip) AS ansible_host, TagTree.tag AS main_group, ParentTag.tag AS parent_group \
    FROM AttributeValue \
    LEFT JOIN Object ON Object.id = AttributeValue.object_id \
    LEFT JOIN IPv4Allocation ON Object.id = IPv4Allocation.object_id AND IPv4Allocation.name = 'eth' \
    LEFT JOIN TagStorage ON TagStorage.entity_id = Object.id \
    LEFT JOIN TagTree ON TagStorage.tag_id = TagTree.id \
    LEFT JOIN TagTree AS ParentTag ON TagTree.parent_id = ParentTag.id \
    WHERE attr_id = 3 AND TagStorage.entity_realm = 'object' AND Object.id IN \
    (SELECT Object.id FROM AttributeValue LEFT JOIN Object ON Object.id = AttributeValue.object_id WHERE attr_id=10005 AND uint_value=1501) \
    ORDER BY Object.name"

cursor = db.cursor()
cursor.execute(sql)
data = cursor.fetchall()
groups = {}
hosts = {}
for rec in data:
    name, ansible_host, main_group, parent_group = rec
    add_item(groups, parent_group, main_group)
    add_item(hosts, main_group, {name: {"ansible_host": ansible_host}})
    group_from_name = main_group[:main_group.find('_')]
    second_group_from_name = ''
    rest_name = main_group[main_group.find('_') + 1:]
    if main_group.count('_') > 1 :
        second_group_from_name = rest_name[:rest_name.find('_')]
    else:
        second_group_from_name = rest_name
    if group_from_name != '':
        add_item(groups, group_from_name, main_group)
    if second_group_from_name != '':
        add_item(groups, second_group_from_name, main_group)

inventory = {}
for group in groups:
    for subgroup in groups[group]:
        inventory.setdefault(group, {}).setdefault('children', []).append(subgroup)
for host_group in hosts:
    for host in hosts[host_group]:
        for name in host:
            inventory.setdefault(host_group, {}).setdefault('hosts', []).append(name)
            inventory.setdefault("_meta", {}).setdefault("hostvars", {})[name] = host[name]
print(json.dumps(inventory, sort_keys=True, indent=2))
db.close()