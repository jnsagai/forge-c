"""Stop only the proven dedicated M7 verifier group, even during threaded unwind.

Bubblewrap teardown is independently exercised. Podman/conmon teardown is not
qualified by this guard and is refused; process-group membership alone does not
prove container quiescence. This creates no repair or deployment authority.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
import signal
import threading

from .durable import Refused
from .operations import Intent
from .verification_job import identity


def owned_group(queue, job_id):
    row = queue.get(job_id)
    current = identity()
    if (not row or row['state'] != 'RUNNING' or not current
            or row['record'].get('owner') != current
            or row['record'].get('managed_process_group') is not True
            or os.getpgid(current['pid']) != current['pid']
            or os.getsid(current['pid']) != current['pid']):
        return None
    return current


def terminate(owner):
    """No DB/CLI/wait in the deadline handler: never wait for a verifier thread."""
    if (owner and identity(owner['pid']) == owner and owner['pid'] == os.getpid()
            and os.getpgid(owner['pid']) == owner['pid'] and os.getsid(owner['pid']) == owner['pid']):
        os.killpg(owner['pid'], signal.SIGKILL)
    raise Refused('LINE_MAINTENANCE_MANAGED_GROUP_UNCONFIRMED')


def require_backend():
    from ..reliability import isolation

    if isolation.backend() != 'bubblewrap':
        raise Refused('LINE_MAINTENANCE_BACKEND_TEARDOWN_NOT_QUALIFIED')


@contextmanager
def watch_intent(owner, job):
    require_backend()
    raw = (job.get('native_context') or {}).get('FORGE_OPERATIONS_INTENT')
    intent = Intent(raw) if raw and os.path.isabs(raw) else None

    def allowed():
        rec = intent.read() if intent else {}
        return rec.get('mode') == 'RUNNING' and rec.get('epoch') == job.get('operations_epoch')

    if not allowed():
        raise Refused('LINE_MAINTENANCE_OPERATIONS_CHANGED')
    stop = threading.Event()

    def monitor():
        while not stop.wait(.05):
            if not allowed():
                terminate(owner)

    thread = threading.Thread(target=monitor, name='line-verifier-intent', daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1)
