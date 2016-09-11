#!/usr/bin/env python3
import paramiko
from scp import SCPClient
import os
import telnetlib
import mysql.connector
import time
import subprocess
import os.path
import glob
from argparse import ArgumentParser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

cfg_tftp = '192.168.100.210'
cfg_tftp_path = '/srv/tftp/'
cfg_pause = 10
cfg_backup_path = '/var/www/rack/wwwroot/configs/'
cfg_temp_path = '/var/www/rack/wwwroot/configs/temp/'
cfg_rack_secret = '/var/www/rack/wwwroot/inc/secret.php'

# mikrotik
cfg_mk_def_port = 7772

# default login/pass
cfg_def_login = 'admin'
cfg_def_pass = 'vtufgfccdjhl'

# racktables attrs id
cfg_rack_login_id = 10000
cfg_rack_pass_id = 10001
cfg_rack_port_id = 10002

# status constants
ST_ER = 0  # error
ST_OK = 1  # ok
ST_CH = 2  # change


def log_msg(msg):
    log_file.write(msg+'\n')
    log_file.flush()
    if not args.noconsole:
        print(msg)


def ssh_exec(client, cmd):
    chan = client.get_transport().open_session()
    chan.exec_command(cmd)
    while chan.recv(255):
        pass
    chan.close()


def insert_sql_data(comment, fname, obj_id):
    cursor_cfg = db.cursor()
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    cursor_cfg.execute('insert into ObjectConfigs(object_id,config,comments,date) values (%s,%s,%s,%s)', (obj_id, fname, comment, now))
    db.commit()


def backup_mikrotik(obj_name, obj_ip, obj_id, obj_mod, obj_port, obj_login, obj_pass):
    ret = ST_OK
    log_msg(' ... getting config from device MikroTik ' + obj_mod)
    fname = obj_name + '.mikrotik'
    fname_export = fname + '.rsc'
    fname_backup = fname + '.backup'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=obj_ip, username=obj_login, password=obj_pass, port=obj_port, allow_agent=False, look_for_keys=False)
        ssh_exec(client, 'export file=' + fname)
        ssh_exec(client, 'system backup save name=' + fname)
        transport = paramiko.Transport((obj_ip, obj_port))
        transport.connect(username=obj_login, password=obj_pass)
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.get('/' + fname_export, cfg_temp_path + fname_export)
        sftp.get('/' + fname_backup, cfg_temp_path + fname_backup)
        sftp.close()
        transport.close()
        ssh_exec(client, 'file remove "' + fname_export + '"')
        ssh_exec(client, 'file remove "' + fname_backup + '"')
        client.close()
        # getting files done - checking old config files
        log_msg(' ... getting config done')
        cursor_cfg = db.cursor()
        cursor_cfg.execute('select config from ObjectConfigs where object_id=%s and comments=%s order by date desc limit 1', (obj_id, 'export'))
        data_cfg = cursor_cfg.fetchall()
        prev_config = ''
        for rec_cfg in data_cfg:
            prev_config, = rec_cfg
        if prev_config != '':
            diff_file = open(cfg_temp_path+'diff.rsc', 'w')
            proc = subprocess.Popen(['/usr/bin/diff', '-I', 'by Router', '-I', 'set wf', '-I', 'CAPsMAN', cfg_backup_path + prev_config, cfg_temp_path + fname_export], stdout=diff_file, stderr=subprocess.PIPE)
            out, err = proc.communicate()
            diff_file.close()
            if proc.returncode != 0:  # diff exist - saving new config
                ret = ST_CH
                log_msg(' ... diff exist - saving new config')
                cursor_cfg.execute('select count(config) from ObjectConfigs where object_id=%s and comments=%s', (obj_id, 'export'))
                data_cfg = cursor_cfg.fetchall()
                n_conf = 0
                for rec_cfg in data_cfg:
                    n_conf, = rec_cfg
                # checking file existing and increase num
                check_done = True
                while check_done:
                    n_conf = n_conf + 1
                    fname_export_new = fname_export[:fname_export.find('rsc')] + str(n_conf) + '.txt'
                    fname_backup_new = fname_backup[:fname_backup.find('backup')] + str(n_conf) + '.backup'
                    fname_diff = fname_export[:fname_export.find('rsc')] + str(n_conf) + '.diff.txt'
                    check_done = os.path.isfile(cfg_backup_path + fname_export_new)
                    check_done = check_done or os.path.isfile(cfg_backup_path + fname_backup_new)
                    check_done = check_done or os.path.isfile(cfg_backup_path + fname_diff)
                os.rename(cfg_temp_path + fname_export, cfg_backup_path + fname_export_new)
                os.rename(cfg_temp_path + fname_backup, cfg_backup_path + fname_backup_new)
                os.rename(cfg_temp_path + 'diff.rsc', cfg_backup_path + fname_diff)
                global g_diff
                g_diff = fname_diff
                insert_sql_data('diff', fname_diff, obj_id)
                insert_sql_data('export', fname_export_new, obj_id)
                insert_sql_data('backup', fname_backup_new, obj_id)
            else:  # clean temp files and do notning
                log_msg(' ... config not changed - do nothing')
                os.remove(cfg_temp_path + fname_export)
                os.remove(cfg_temp_path + fname_backup)
                os.remove(cfg_temp_path + 'diff.rsc')
        else:  # 1st config
            log_msg(' ... config not exist - saving first config')
            fname_export_new = fname_export[:fname_export.find('rsc')] + '1.txt'
            fname_backup_new = fname_backup[:fname_backup.find('backup')] + '1.backup'
            os.rename(cfg_temp_path + fname_export, cfg_backup_path + fname_export_new)
            os.rename(cfg_temp_path + fname_backup, cfg_backup_path + fname_backup_new)
            insert_sql_data('export', fname_export_new, obj_id)
            insert_sql_data('backup', fname_backup_new, obj_id)
        return ret
    except:
        return ST_ER


def save_tftp_config(fname, obj_id):
    ret = ST_OK
    try:
        cfg_done = os.path.isfile(cfg_tftp_path + fname)
        if cfg_done:
            log_msg(' ... getting config done')
        else:
            log_msg(' ... getting config error')
            return ST_ER
        cursor_cfg = db.cursor()
        cursor_cfg.execute('select config from ObjectConfigs where object_id=%s and comments=%s order by date desc limit 1', (obj_id, 'config'))
        data_cfg = cursor_cfg.fetchall()
        prev_config = ''
        for rec_cfg in data_cfg:
            prev_config, = rec_cfg
        if prev_config != '':
            diff_file = open(cfg_temp_path + 'diff.rsc', 'w')
            proc = subprocess.Popen(['/usr/bin/diff', cfg_backup_path + prev_config, cfg_tftp_path + fname], stdout=diff_file, stderr=subprocess.PIPE)
            out, err = proc.communicate()
            diff_file.close()
            if proc.returncode != 0:  # diff exist - saving new config
                log_msg(' ... diff exist - saving new config')
                ret = ST_CH
                cursor_cfg.execute('select count(config) from ObjectConfigs where object_id=%s and comments=%s', (obj_id, 'config'))
                data_cfg = cursor_cfg.fetchall()
                n_conf = 0
                for rec_cfg in data_cfg:
                    n_conf, = rec_cfg
                # checking file existing and increase num
                check_done = True
                while check_done:
                    n_conf = n_conf+1
                    fname_new = fname[:fname.find('txt')] + str(n_conf) + '.txt'
                    fname_diff = fname[:fname.find('txt')] + str(n_conf) + '.diff.txt'
                    check_done = os.path.isfile(cfg_backup_path + fname_new)
                    check_done = check_done or os.path.isfile(cfg_backup_path + fname_diff)
                os.rename(cfg_tftp_path + fname, cfg_backup_path + fname_new)
                os.rename(cfg_temp_path + 'diff.rsc', cfg_backup_path + fname_diff)
                global g_diff
                g_diff = fname_diff
                insert_sql_data('diff', fname_diff, obj_id)
                insert_sql_data('config', fname_new, obj_id)
            else:  # clean temp files and do notning
                log_msg(' ... config not changed - do nothing')
                os.remove(cfg_tftp_path+fname)
                os.remove(cfg_temp_path+'diff.rsc')
        else:  # 1st config
            log_msg(' ... config not exist - saving first config')
            fname_new = fname[:fname.find('txt')] + '1.txt'
            os.rename(cfg_tftp_path + fname, cfg_backup_path + fname_new)
            insert_sql_data('config', fname_new, obj_id)
        return ret
    except:
        return ST_ER


def backup_dlink_sw(obj_name, obj_ip, obj_id, obj_mod, obj_login, obj_pass):
    try:
        log_msg(' ... getting config from device D-Link '+obj_mod)
        fname = obj_name + '.' + obj_mod.lower() + '.txt'
        client = telnetlib.Telnet(obj_ip)
        client.read_until(b':', cfg_pause)
        client.write((obj_login + '\n').encode('utf-8'))
        client.read_until(b':', cfg_pause)
        client.write((obj_pass+'\n').encode('utf-8'))
        client.read_until(b'#', cfg_pause)
        client.write(b'\n')
        client.read_until(b'#', cfg_pause)
        if (obj_mod == 'DGS-3100-24TG') or (obj_mod == 'DGS-3100-48'):
            upload_cmd = 'upload configuration ' + cfg_tftp + ' ' + fname + '\n'
            client.write(upload_cmd.encode('utf-8'))
            client.read_until(b'!', cfg_pause)
            time.sleep(1)
        elif (obj_mod == 'DES-3026'):
            upload_cmd = 'upload configuration ' + cfg_tftp + ' ' + fname + '\n'
            client.write(upload_cmd.encode('utf-8'))
            client.read_until(b'#', cfg_pause)
            time.sleep(1)
        elif (obj_mod == 'DGS-3120-24SC'):
            upload_cmd = 'upload cfg_toTFTP ' + cfg_tftp + ' dest_file ' + fname + '\n'
            client.write(upload_cmd.encode('utf-8'))
            client.read_until(b'Success.', cfg_pause)
            time.sleep(1)
        else:
            upload_cmd = 'upload cfg_toTFTP ' + cfg_tftp + ' ' + fname + '\n'
            client.write(upload_cmd.encode('utf-8'))
            client.read_until(b'#', cfg_pause)
            cfg_done = os.path.isfile(cfg_tftp_path + fname)
            if not cfg_done:
                upload_cmd = 'upload cfg_toTFTP ' + cfg_tftp + ' dest_file ' + fname + '\n'
                client.write(upload_cmd.encode('utf-8'))
                client.read_until(b'#', cfg_pause)
        client.write(b'logout\n')
        client.close()
        return save_tftp_config(fname, obj_id)
    except:
        return ST_ER


def backup_dlink_wf(obj_name, obj_ip, obj_id, obj_mod, obj_login, obj_pass):
    try:
        log_msg(' ... getting config from device D-Link '+obj_mod)
        fname = obj_name + '.' + obj_mod.lower() + '.txt'
        client = telnetlib.Telnet(obj_ip)
        client.read_until(b':', cfg_pause)
        client.write((obj_login+'\n').encode('utf-8'))
        client.read_until(b':', cfg_pause)
        client.write((obj_pass+'\n').encode('utf-8'))
        client.read_until(b'>', cfg_pause)
        client.write(('tftp srvip ' + cfg_tftp + '\n').encode('utf-8'))
        client.read_until(b'>')
        client.write(('tftp uploadtxt ' + fname + '\n').encode('utf-8'))
        client.read_until(b'>')
        client.write(b'quit\n')
        client.close()
        return save_tftp_config(fname, obj_id)
    except:
        return ST_ER


def backup_cisco(obj_name, obj_ip, obj_id, obj_mod, obj_login, obj_pass):
    try:
        log_msg(' ... getting config from device Cisco '+obj_mod)
        fname = obj_name + '.' + obj_mod.lower() + '.txt'
        client = telnetlib.Telnet(obj_ip)
        client.read_until(b':', cfg_pause)
        client.write((obj_login+'\n').encode('utf-8'))
        client.read_until(b':', cfg_pause)
        client.write((obj_pass+'\n').encode('utf-8'))
        client.read_until(b'#', cfg_pause)
        client.write(('copy startup-config tftp://'+cfg_tftp+'/'+fname+'\n').encode('utf-8'))
        client.read_until(b'?', cfg_pause)
        client.write(b'\n')
        client.read_until(b'?', cfg_pause)
        client.write(b'\n')
        client.read_until(b'#')
        client.write(b'logout\n')
        client.close()
        return save_tftp_config(fname, obj_id)
    except:
        return ST_ER


def backup_ubiquiti(obj_name, obj_ip, obj_id, obj_mod, obj_login, obj_pass):
    try:
        log_msg(' ... getting config from device Ubiquiti '+obj_mod)
        fname = obj_name + '.ubiquiti.txt'
        transport = paramiko.Transport((obj_ip, 22))
        transport.connect(username=obj_login, password=obj_pass)
        scp = SCPClient(transport)
        scp.get('/tmp/system.cfg', cfg_tftp_path + fname)
        scp.close()
        transport.close()
        return save_tftp_config(fname, obj_id)
    except IOError:
        return ST_ER


def rack_get_attr(obj_id, attr_id):
    cursor = db.cursor()
    cursor.execute('select string_value from AttributeValue where object_id=%s and attr_id=%s', (obj_id, attr_id))
    data = cursor.fetchall()
    value = ''
    for rec in data:
        value, = rec
    cursor.close()
    return value

# main program
parser = ArgumentParser(description='script for backup device configs')
parser.add_argument('--noconsole', action='store_true', help='run in detached mode')
parser.add_argument('--oid', type=int, default=0, help='backup config for specific object id')
args = parser.parse_args()

# clean temp directories
files = glob.glob(cfg_temp_path+'*')
for f in files:
    os.remove(f)
files = glob.glob(cfg_tftp_path+'*')
for f in files:
    os.remove(f)

log_file_name = cfg_temp_path + 'backup_log.txt'
log_file = open(log_file_name, 'w+')

# get settings from racktables config file
rack_secret = open(cfg_rack_secret, 'r')
rack_host = rack_db = rack_user = rack_pass = ''
for line in rack_secret:
    if line.find('pdo_dsn') > 0:
        rack_host = line[line.find(':host=')+6:line.find(';dbname=')]
        rack_db = line[line.find(';dbname=')+8:line.find('\';')]
    if line.find('db_username') > 0:
        rack_user = line[line.find('\'')+1:line.find('\';')]
    if line.find('db_password') > 0:
        rack_pass = line[line.find('\'')+1:line.find('\';')]
rack_secret.close()

db = mysql.connector.connect(host=rack_host, user=rack_user, passwd=rack_pass, db=rack_db, charset='utf8')
if args.oid == 0:
    sql = 'select AttributeValue.string_value,Object.id,Object.name from AttributeValue \
    left join Object on Object.id=AttributeValue.object_id where attr_id=3 and name not like "ipc%"'
else:
    sql = 'select AttributeValue.string_value,Object.id,Object.name from AttributeValue \
    left join Object on Object.id=AttributeValue.object_id where attr_id=3 and Object.id={}'.format(args.oid)
cursor = db.cursor()
cursor.execute(sql)

n_ok = 0  # ok
n_er = 0  # error
n_ch = 0  # change
data = cursor.fetchall()
log_table = (())
g_diff = ''

for rec in data:
    obj_ip, obj_id, obj_name = rec
    sql = 'select AM.attr_id, D.dict_value, O.id as object_id from Object as O \
    left join AttributeMap as AM on O.objtype_id = AM.objtype_id \
    left join AttributeValue as AV on AV.attr_id = AM.attr_id and AV.object_id = O.id \
    left join Dictionary as D on D.dict_key = AV.uint_value and AM.chapter_id = D.chapter_id \
    where AM.attr_id=2 and object_id={}'.format(obj_id)
    cursor_hw = db.cursor()
    cursor_hw.execute(sql)
    data_hw = cursor_hw.fetchall()
    for rec_hw in data_hw:
        obj_attr_id, obj_hw, obj_id = rec_hw

    if obj_hw.find('[[') >= 0:
        obj_hw = obj_hw[2:obj_hw.find(' | ')]
    obj_man = obj_hw[:obj_hw.find('%GPASS%')]
    obj_mod = obj_hw[obj_hw.find('%GPASS%')+7:]
    log_msg('{} {} backup config ...'.format(obj_name, obj_ip))

    g_diff = ''
    status = ST_ER

    obj_login = rack_get_attr(obj_id, cfg_rack_login_id)
    obj_pass = rack_get_attr(obj_id, cfg_rack_pass_id)
    if obj_login == '':
        obj_login = cfg_def_login
    if obj_pass == '':
        obj_pass = cfg_def_pass

    if obj_man == 'MikroTik':
        obj_port = rack_get_attr(obj_id, cfg_rack_port_id)
        if obj_port == '':
            obj_port = cfg_mk_def_port
        else:
            obj_port = int(obj_port)
        status = backup_mikrotik(obj_name, obj_ip, obj_id, obj_mod, obj_port, obj_login, obj_pass)

    if (obj_man == 'D-Link') and (obj_mod != 'DWL-3260AP'):
        status = backup_dlink_sw(obj_name, obj_ip, obj_id, obj_mod, obj_login, obj_pass)

    if (obj_man == 'D-Link') and (obj_mod == 'DWL-3260AP'):
        status = backup_dlink_wf(obj_name, obj_ip, obj_id, obj_mod, obj_login, obj_pass)

    if obj_man == 'Cisco':
        status = backup_cisco(obj_name, obj_ip, obj_id, obj_mod, obj_login, obj_pass)

    if obj_man == 'Ubiquiti':
        status = backup_ubiquiti(obj_name, obj_ip, obj_id, obj_mod, obj_login, obj_pass)

    if (status == ST_OK):
        log_status = 'OK'
        n_ok = n_ok + 1
    elif (status == ST_ER):
        log_status = 'ERROR'
        n_er = n_er + 1
    else:
        log_status = 'CHANGE'
        n_ch = n_ch + 1

    log_msg(log_status)
    log_table = log_table + ((obj_id, obj_name, obj_ip, log_status, g_diff),)

db.close()
log_msg('{} DEV | {} OK | {} CH | {} ERR'.format(n_er + n_ok + n_ch, n_ok, n_ch, n_er))
log_file.close()

if ((n_er + n_ch) > 0) and (args.oid == 0):
    msg = MIMEMultipart()
    if (n_er == 0) and (n_ch > 0):
        msg['Subject'] = 'Backup configs CHANGED'
    elif (n_er > 0) and (n_ch == 0):
        msg['Subject'] = 'Backup configs FAILED'
    else:
        msg['Subject'] = 'Backup configs FAILED or CHANGED'
    msg['From'] = 'root@rack.sz'
    msg['To'] = 'ph@dvorpodznoeva.ru'
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(open(log_file_name, 'rb').read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename="backup_log.txt"')
    msg.attach(part)
    tx = '<html><table border=1><th>Name</th><th>IP</th><th>Status</th><th>Diff</th>'

    for rec_log in log_table:
        obj_id, obj_name, obj_ip, log_status, g_diff = rec_log
        if log_status != 'OK':
            tx = tx + '<tr><td><a href="http://rack.sz/index.php?page=object&object_id={}">{}</a></td><td>{}</td><td>{}</td><td><a href="http://rack.sz/configs/{}">{}</a></td></tr>'.format(obj_id, obj_name, obj_ip, log_status, g_diff, g_diff)
    tx = tx + '</table></html>'
    msg.attach(MIMEText(tx, 'html'))
    server = smtplib.SMTP('mail.dvorpodznoeva.ru')
    server.sendmail('root@rack.sz', 'ph@dvorpodznoeva.ru', msg.as_string())

time.sleep(5)
os.remove(log_file_name)
