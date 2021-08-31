#!/usr/bin/env python3
import yaml
import json
import sys

if len(sys.argv) < 2:
    sys.exit(0)
config_file = sys.argv[1]

with open(config_file, 'r') as open_yaml:
    config = yaml.safe_load(open_yaml)
    ports = config['ports']
    vlans = {}
    for port in ports:
        if port['type'] == 'access':
            if vlans.get(port['vlan']) == None:
                vlans[port['vlan']] = {'untagged': port['name'],
                                       'tagged': ''}
            else:
                if vlans[port['vlan']]['untagged'] != '':
                    vlans[port['vlan']] = {'untagged': vlans[port['vlan']]['untagged'] + ',' + port['name'],
                                           'tagged': vlans[port['vlan']]['tagged']}
                else:
                    vlans[port['vlan']] = {'untagged': port['name'],
                                           'tagged': vlans[port['vlan']]['tagged']}
        else:
            if port['vlan'] == None:
                continue
            try:
                port_vlans = [int(x) for x in port['vlan'].split(",")]
            except AttributeError:
                port_vlans = [int(port['vlan'])]
            for port_vlan in port_vlans:
                if vlans.get(port_vlan) == None:
                    vlans[port_vlan] = {'untagged': '',
                                        'tagged': port['name']}
                else:
                    if vlans[port_vlan]['tagged'] != '':
                        vlans[port_vlan] = {'untagged': vlans[port_vlan]['untagged'],
                                            'tagged': vlans[port_vlan]['tagged'] + ',' + port['name']}
                    else:
                        vlans[port_vlan] = {'untagged': vlans[port_vlan]['untagged'],
                                            'tagged': port['name']}
    print(json.dumps(vlans))
