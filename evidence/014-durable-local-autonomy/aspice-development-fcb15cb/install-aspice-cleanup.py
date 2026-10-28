from pathlib import Path
import os,subprocess
P=Path('/mnt/data/forge-c/production-local-014');D=P/'deployment';O=D/'aspice-window-20261028'
name='forge-aspice-expiry-20261028'
service='''[Unit]
Description=Restore original policy after bounded ASPICE qualification (operator epoch fenced)
[Service]
Type=oneshot
ExecStart=/mnt/data/forge-c/production-local-014/venv/bin/python /mnt/data/forge-c/production-local-014/deployment/restore-aspice-window.py
'''
timer='''[Unit]
Description=Bounded ASPICE window cleanup without stopping factory
[Timer]
OnCalendar=2026-10-28 16:29:15 UTC
Persistent=true
AccuracySec=1s
Unit=forge-aspice-expiry-20261028.service
[Install]
WantedBy=timers.target
'''
for suffix,data in [('service',service),('timer',timer)]:
 src=O/(name+'.'+suffix);src.write_text(data);src.chmod(0o600)
 dst=Path.home()/'.config/systemd/user'/src.name
 assert not dst.exists();dst.symlink_to(src)
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
subprocess.run(['systemctl','--user','enable','--now',name+'.timer'],check=True)
print('ASPICE_EXPIRY_TIMER_INSTALLED')
