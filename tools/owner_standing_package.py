"""External owner administration: adapt the reviewed host start package to standing time.

No issuance, start, shell execution or policy changes. Every old source/receipt/stop/
namespace/quality check remains in the generated helpers. Unknown shapes refuse.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('OWNER_PACKAGE_SHAPE_CHANGED:' + old[:80])
    return source.replace(old, new)


def standing_start(source):
    source = replace_once(source, "a.add_argument('--start-reviewed',action='store_true');a.add_argument('--ticket',type=Path)",
                          "a.add_argument('--start-reviewed',action='store_true');a.add_argument('--ticket',type=Path)\n"
                          "    a.add_argument('--until-owner-stop',action='store_true')")
    old = ("    need(x.ticket is not None and x.ticket.resolve().parent==R/'owner-main-ops','FRESH_TICKET_LOCATION_REQUIRED')\n"
           "    ticket=checked_json(x.ticket,x.ticket_sha256);D.validate_expiry_ticket(ticket,1795057626.0)")
    new = """    need(x.until_owner_stop and x.ticket is None and x.ticket_sha256 is None,'EXPLICIT_STANDING_MODE_REQUIRED')
    def require_standing_time():
        from forge_factory.afo.mission_lifetime import LIFETIME
        from forge_factory.afo.queue import Store
        mission,_=D._mission(Store(F/'lrtx/state/supervisor/line-queue.sqlite3',must_exist=True),
                             json.loads((DATA/'control/line-recovery-control.development.json').read_bytes()))
        need(mission['limits'].get('authorization_lifetime')==LIFETIME and mission['limits']['deadline'] is None,
             'OWNER_STANDING_AUTHORITY_REQUIRED')
    require_standing_time()"""
    source = replace_once(source, old, new)
    if source.count('D.validate_expiry_ticket(ticket,1795057626.0)') != 2:
        raise ValueError('OWNER_PACKAGE_FINAL_TIME_FENCES_CHANGED')
    source = source.replace('D.validate_expiry_ticket(ticket,1795057626.0)', 'require_standing_time()')
    source = replace_once(source, "'--expiry-ticket',str(x.ticket),", '')
    compile(source, '<standing-owner-start>', 'exec')
    return source


def standing_launcher(source):
    values = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    if any(not isinstance(values.get(k), str) for k in ('T', 'PY', 'RET', 'HARD')):
        raise ValueError('OWNER_PACKAGE_LAUNCHER_BINDINGS_CHANGED')
    hashes = re.findall(r"([pb])\.read_bytes\(\)\)\.hexdigest\(\)=='([0-9a-f]{64})'", source)
    if sorted(k for k, _ in hashes) != ['b', 'p']:
        raise ValueError('OWNER_PACKAGE_LAUNCHER_HASH_BINDINGS_CHANGED')
    hashes = dict(hashes)
    return f'''"""Exactly-once host-owner standing start. No calendar renewal or network date service."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
O=Path(__file__).resolve().parent
R=Path({values['T']!r});PY={values['PY']!r}
RET={values['RET']!r};HARD={values['HARD']!r}
STOP,META=sys.argv[1:3];assert len(STOP)==len(META)==64
for key in ('FORGE_AGENT_ROLE','FORGE_WORKSPACE','FORGE_POLICY_BINDING','FORGE_OWNER_DEVELOPMENT_RECORD',
            'FORGE_OWNER_DEVELOPMENT_SHA256','FORGE_LINE_STACK_PAYLOAD','FORGE_LINE_STACK_PAYLOAD_SHA256','FORGE_STACK_LOCK_FD'):
    assert not os.environ.get(key),'FORBIDDEN_CALLER_CONTEXT'
p=R/'owner-main-ops/start-main-reviewed.py';b=R/'owner-main-ops/binding.json'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='{hashes['p']}'
assert hashlib.sha256(b.read_bytes()).hexdigest()=='{hashes['b']}'
assert os.environ.get('XDG_RUNTIME_DIR') and os.environ.get('DBUS_SESSION_BUS_ADDRESS'),'REAL_USER_BUS_MISSING'
env={{k:os.environ[k] for k in ('HOME','USER','LOGNAME','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS','LANG') if k in os.environ}}
env.update(PATH='/usr/local/bin:/usr/bin:/bin',PYTHONDONTWRITEBYTECODE='1')
with (O/'start-request-intent-r1.json').open('x') as f:
    os.fchmod(f.fileno(),0o600)
    json.dump(dict(state='EXACT_ONCE_STANDING_START_POSSIBLE_EFFECTS_NO_REPLAY',authorization_lifetime='UNTIL_OWNER_STOP',
                   stop_result_sha256=STOP,metadata_result_sha256=META),f);f.flush();os.fsync(f.fileno())
D=R/'owner-main-preflight-r1';D.mkdir(mode=0o700,exist_ok=True)
out=open(D/'start-r1.stdout.log','xb');err=open(D/'start-r1.stderr.log','xb')
cmd=[PY,str(p),'--start-reviewed','--until-owner-stop','--retirement-sha256',RET,'--hardening-sha256',HARD,
     '--metadata-receipt-sha256',META,'--stop-result-sha256',STOP]
sh='"$@"; echo $? > '+str(D/'start-r1.exit')
proc=subprocess.Popen(['setsid','nohup','bash','-c',sh,'start-once',*cmd],env=env,cwd='/',
                      stdin=subprocess.DEVNULL,stdout=out,stderr=err,close_fds=True)
print(json.dumps(dict(status='STANDING_START_DETACHED',pid=proc.pid,authorization_lifetime='UNTIL_OWNER_STOP')))
'''


def retirement_cursor(source):
    """The maintenance window can legitimately clear paused; all other unknown controls still refuse."""
    return replace_once(source, "('paused',HOLD)) for x in allowed)",
                        "('paused',HOLD),('paused','model-service-qualification-window')) for x in allowed)")


def adapt(package):
    package = Path(package)
    paths = ['ops/start-main-reviewed.py', 'start-with-fresh-ticket-once-r1.py', 'bind-main.py']
    original = {name: (package / name).read_text() for name in paths}
    updated = dict(original)
    updated[paths[0]] = standing_start(original[paths[0]])
    updated[paths[1]] = standing_launcher(original[paths[1]])
    updated[paths[2]] = replace_once(original[paths[2]], 'fixed_deadline=1795057626,',
                                    "authorization_lifetime='UNTIL_OWNER_STOP',historical_deadline=1795057626,")
    for name, source in updated.items():
        compile(source, name, 'exec')
    # Validate every shape before changing any file. Caller uses an isolated generated package.
    report = {}
    for name in paths:
        (package / name).write_text(updated[name])
        report[name] = dict(before_sha256=hashlib.sha256(original[name].encode()).hexdigest(),
                            after_sha256=hashlib.sha256(updated[name].encode()).hexdigest())
    (package / 'standing-time-adaptation.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(adapt(args.package), sort_keys=True))
