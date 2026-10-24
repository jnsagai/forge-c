from pathlib import Path
import subprocess,json
root=Path('/mnt/data/forge-c/lrtx-v2/state/operator-runs/feature013')
unit=Path.home()/'.config/systemd/user/forge-conductor-local-omniverse2.service'
unit.parent.mkdir(parents=True,exist_ok=True)
assert not unit.exists(),'Refuse overwriting existing unit'
unit.write_text('''[Unit]
Description=Forge-C owner-authorized local Qwen mission conductor
RequiresMountsFor=/mnt/data/forge-c
After=default.target
StartLimitIntervalSec=600
StartLimitBurst=5

[Service]
Type=notify
NotifyAccess=all
ExecStart=/usr/bin/python3 /mnt/data/forge-c/lrtx-v2/state/operator-runs/feature013/feature013-remote-exec.py -m forge_factory.afo.conductor
Restart=on-failure
RestartSec=15
WatchdogSec=300
TimeoutStartSec=300
TimeoutStopSec=45
Nice=5
CPUWeight=80
MemoryHigh=72G
MemoryMax=88G
UMask=0077

[Install]
WantedBy=default.target
''')
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
subprocess.run(['systemctl','--user','enable','--now','forge-conductor-local-omniverse2.service'],check=True)
p=subprocess.run(['systemctl','--user','show','forge-conductor-local-omniverse2.service','--property=ActiveState,SubState,MainPID,Result,NRestarts'],capture_output=True,text=True,check=True)
print(p.stdout)
