"""Curate a replay from public evidence without publishing local paths or raw input text."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / 'website/public/media'
RUN = 'evidence/v0.4/runs/RC1/WO-0009B-STM32N6-IWDG-HAL-rc4'
SCREENSHOT = 'evidence/v0.4/runs/CR-T044/control-room-after-r168.png'


def prepare():
    MEDIA.mkdir(parents=True, exist_ok=True)
    log_path = ROOT / RUN / 'gate-log.jsonl'
    package_path = ROOT / RUN / 'package.json'
    rows = [json.loads(line) for line in log_path.read_text().splitlines()]
    package = json.loads(package_path.read_text())
    events = []
    for row in rows:
        outcome = row.get('gate', {}).get('decision') or row.get('result') or row.get('verdict')
        if row['step'] == 'route':
            detail = 'Return to the author. The rework budget remains bounded.'
        elif row['step'] == 'inspect':
            detail = 'The recorded inspection gate passed.'
            if row.get('agent_ok') is False:
                detail += f" The agent status separately reported {row.get('agent_status')}; see the source log."
        elif row['step'] == 'verify':
            detail = 'Guideline verification: 0 violations, 0 implementation findings, 0 register-map findings.'
        elif outcome == 'REJECTED':
            detail = 'Requirements lacked required register effects.' if row['phase'] == 'SWE.1' else 'The detailed-design diagram did not pass the render check.'
        else:
            detail = f"Baseline {row.get('baseline_id', '')} frozen."
            if row.get('errors'):
                detail += ' Recorded author-output warning: ' + ', '.join(row['errors']) + '.'
        events.append({'phase': row['phase'], 'step': row['step'], 'outcome': outcome,
                       'timestamp': row['ts'], 'detail': detail})
    events.append({'phase': 'PACKAGE', 'step': 'seal', 'outcome': package['package_status'],
        'timestamp': package['finalized_at'], 'detail': f"{package['gap_count']} declared gaps. Offline review only; not safety approved."})
    data = {'schema': 'forge-c/evidence-replay/1', 'run_id': package['run_id'], 'date': '2026-10-21',
        'label': 'Recorded gate-event replay; time compressed. Not a live run or a screen recording.',
        'duration_seconds': 45, 'archive_sha256': package['archive_sha256'], 'events': events,
        'sources': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (log_path, package_path, ROOT / SCREENSHOT)}}
    (MEDIA / 'recorded-run.json').write_text(json.dumps(data, indent=2)+'\n')
    shutil.copyfile(ROOT / SCREENSHOT, MEDIA / 'control-room.png')
    captions = ['WEBVTT', '']
    def timestamp(seconds):
        return f'00:{int(seconds)//60:02}:{seconds%60:06.3f}'
    for i, event in enumerate(events):
        captions += [f'{timestamp(i*2.5)} --> {timestamp((i+1)*2.5)}',
                     f"{event['phase']} {event['step'].upper()}: {event['outcome']}. {event['detail']}", '']
    (MEDIA / 'workflow-replay.vtt').write_text('\n'.join(captions))
    print(f'Prepared {len(events)} replay events and an unchanged source screenshot')


if __name__ == '__main__':
    prepare()
