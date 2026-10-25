"""DA-013: native liveness is independent of terminal business outcome.

A transport cancel acknowledgment is never termination evidence. No listing gap,
lease timeout, or idle GPU observation releases the inference owner.
"""
from __future__ import annotations

import json

from ..common import utc_now
from ..fabro.client import run_status
from .durable import Refused, canonical, digest, validate
from .mission_ledger import MissionLedger

TERMINAL_NATIVE = {'SUCCEEDED', 'FAILED', 'CANCELLED', 'CANCELED'}


class Executions:
    def __init__(self, store):
        self.store = store

    def get(self, job_id: str) -> dict | None:
        with self.store.tx() as c:
            row = c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?', (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def reserve(self, job_id: str, mission_id: str, nonce: str) -> dict:
        old = self.get(job_id)
        if old:
            if old['mission_id'] != mission_id or old['launch_nonce'] != nonce:
                raise Refused('EXECUTION_IDENTITY_REBOUND')
            return old
        epoch = MissionLedger(self.store).acquire_inference(job_id, mission_id)
        rec = {'schema_version': '1.0', 'mission_id': mission_id, 'job_id': job_id,
               'execution_id': 'execution-' + digest([mission_id, job_id, nonce])[:24], 'revision': 1,
               'lease_epoch': epoch, 'launch_nonce': nonce, 'authorization_state': 'VALID',
               'admission_state': 'RESERVED', 'identity_state': 'NONE', 'native_run_ids': [],
               'execution_liveness': 'NOT_STARTED', 'cancellation_state': 'NOT_REQUESTED',
               'cancel_attempts': 0, 'last_cancel_error': None, 'resource_lease': 'HELD',
               'task_outcome': 'ACTIVE', 'terminal_reason': None, 'quiescence_evidence_ref': None,
               'outcome_evidence_ref': None, 'last_reconciled_at': None}
        validate('execution-lifecycle', rec)
        with self.store.tx() as c:
            c.execute('INSERT OR IGNORE INTO afo_execution_liveness VALUES (?,?,?,?)',
                      (rec['execution_id'], job_id, mission_id, canonical(rec).decode()))
        return self.get(job_id)

    def _write(self, rec: dict, expected_revision: int) -> dict:
        validate('execution-lifecycle', {k: v for k, v in rec.items() if k != 'quiescence_proof'})
        with self.store.tx() as c:
            old = c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?', (rec['job_id'],)).fetchone()
            if not old or json.loads(old[0])['revision'] != expected_revision:
                raise Refused('EXECUTION_FENCE_STALE')
            owner = c.execute("SELECT holder,epoch FROM afo_resource_ownership WHERE resource='inference'").fetchone()
            if rec['resource_lease'] == 'HELD' and (not owner or owner['holder'] != rec['job_id'] or owner['epoch'] != rec['lease_epoch']):
                raise Refused('EXECUTION_LEASE_FENCED')
            rec = {**rec, 'revision': expected_revision + 1, 'last_reconciled_at': utc_now()}
            c.execute('UPDATE afo_execution_liveness SET record=? WHERE job_id=?', (canonical(rec).decode(), rec['job_id']))
        return rec

    def dispatch_intent(self, job_id: str) -> dict:
        rec = self.get(job_id)
        if rec['admission_state'] != 'RESERVED' or rec['authorization_state'] != 'VALID' or rec['task_outcome'] != 'ACTIVE':
            raise Refused('EXECUTION_NOT_DISPATCHABLE')
        return self._write({**rec, 'admission_state': 'DISPATCH_INTENT_RECORDED',
                            'identity_state': 'UNCONFIRMED', 'execution_liveness': 'POSSIBLY_LIVE'}, rec['revision'])

    def adopt(self, job_id: str, run_ids: list[str]) -> dict:
        rec = self.get(job_id)
        ids = sorted(set(rec['native_run_ids']) | set(run_ids))
        if not ids or rec['admission_state'] == 'RESERVED' or rec['resource_lease'] == 'RELEASED':
            raise Refused('NATIVE_ADOPTION_WITHOUT_LIVE_INTENT')
        return self._write({**rec, 'native_run_ids': ids, 'admission_state': 'NATIVE_ACCEPTED',
                            'identity_state': 'CONFIRMED' if len(ids) == 1 else 'AMBIGUOUS',
                            'execution_liveness': 'LIVE' if len(ids) == 1 else 'UNKNOWN'}, rec['revision'])

    def outcome(self, job_id: str, outcome: str, reason: str, evidence_ref: str | None = None) -> dict:
        rec = self.get(job_id)
        if rec['task_outcome'] != 'ACTIVE' and rec['task_outcome'] != outcome:
            raise Refused('TERMINAL_TASK_REENTRY_FORBIDDEN')
        if outcome == 'RECOVERED':
            raise Refused('RECOVERED_REQUIRES_INDEPENDENT_VERIFICATION')
        return self._write({**rec, 'task_outcome': outcome, 'terminal_reason': reason,
                            'outcome_evidence_ref': evidence_ref or 'execution-outcome:' + digest([job_id, outcome, reason]),
                            'cancellation_state': 'REQUESTED' if rec['execution_liveness'] in ('POSSIBLY_LIVE', 'LIVE', 'UNKNOWN')
                            and rec['cancellation_state'] == 'NOT_REQUESTED' else rec['cancellation_state']}, rec['revision'])

    def revoke(self, job_id: str, state='REVOKED') -> dict:
        rec = self.get(job_id)
        if state not in ('REVOKED', 'EXPIRED'):
            raise Refused('AUTHORIZATION_STATE_INVALID')
        return self._write({**rec, 'authorization_state': state,
                            'cancellation_state': 'REQUESTED' if rec['execution_liveness'] in ('POSSIBLY_LIVE', 'LIVE', 'UNKNOWN')
                            and rec['cancellation_state'] == 'NOT_REQUESTED' else rec['cancellation_state']}, rec['revision'])

    def reconcile(self, job_id: str, client, *, cancel=False) -> dict:
        rec = self.get(job_id)
        if rec['resource_lease'] == 'RELEASED':
            return rec
        if rec['execution_liveness'] == 'QUIESCENT' and rec.get('quiescence_proof'):
            MissionLedger(self.store).release_inference(job_id, proof=rec['quiescence_proof'])
            return self._write({**rec, 'resource_lease': 'RELEASED'}, rec['revision'])
        if rec['admission_state'] == 'RESERVED':
            # Dispatch intent and the external effect are ordered; this execution never contacted native Fabro.
            if cancel or rec['authorization_state'] != 'VALID' or rec['task_outcome'] != 'ACTIVE':
                return self._quiescent(rec, {'kind': 'NOT_DISPATCHED', 'evidence_ref': 'execution-intent:' + rec['execution_id']})
            return rec
        if not rec['native_run_ids'] or rec['identity_state'] == 'AMBIGUOUS':
            try:
                hits = [r['id'] for r in client.list_runs(limit=200)
                        if (r.get('labels') or {}).get('afo_agent') == job_id
                        and (r.get('labels') or {}).get('afo_nonce') == rec['launch_nonce']]
                if hits:
                    rec = self.adopt(job_id, hits)
            except Exception:  # noqa: BLE001 - retained uncertainty, never a relaunch permission
                pass
        if not rec['native_run_ids']:
            return self._write({**rec, 'execution_liveness': 'UNKNOWN'}, rec['revision'])
        observations, all_terminal = {}, True
        for rid in rec['native_run_ids']:
            try:
                status = run_status(client.get_run(rid))
            except Exception:  # noqa: BLE001 - unreachable/404 is not proof of native termination
                status = 'UNKNOWN'
            observations[rid] = status
            if status not in TERMINAL_NATIVE:
                all_terminal = False
        # Multiple nonce matches can conceal other dispatch outcomes. A bounded list alone cannot settle that ambiguity.
        if all_terminal and rec['identity_state'] == 'CONFIRMED':
            return self._quiescent(rec, {'kind': 'AUTHORITATIVE_NATIVE_TERMINAL',
                                         'evidence_ref': 'native-terminals:' + digest(observations),
                                         'native_run_ids': rec['native_run_ids'], 'observations': observations})
        if cancel or rec['authorization_state'] != 'VALID' or rec['task_outcome'] != 'ACTIVE':
            rec['cancellation_state'] = 'REQUESTED'
            for rid, status in observations.items():
                if status in TERMINAL_NATIVE:
                    continue
                rec['cancel_attempts'] += 1
                try:
                    code = client.cancel(rid)
                    if code in (200, 202, 204):
                        rec['cancellation_state'] = 'ACKNOWLEDGED'
                        rec['last_cancel_error'] = None
                    else:
                        rec['last_cancel_error'] = f'HTTP_{code}'
                except Exception as exc:  # noqa: BLE001 - cancellation remains pending and visible
                    rec['last_cancel_error'] = type(exc).__name__
        rec['execution_liveness'] = 'LIVE' if all(s != 'UNKNOWN' for s in observations.values()) else 'UNKNOWN'
        return self._write(rec, rec['revision'])

    def _quiescent(self, rec: dict, proof: dict) -> dict:
        rec = self._write({**rec, 'execution_liveness': 'NOT_STARTED' if rec['admission_state'] == 'RESERVED' else 'QUIESCENT',
                           'quiescence_evidence_ref': None if rec['admission_state'] == 'RESERVED' else proof['evidence_ref'],
                           'cancellation_state': 'QUIESCENCE_CONFIRMED' if rec['cancellation_state'] != 'NOT_REQUESTED'
                           or rec['authorization_state'] != 'VALID' else 'NOT_REQUESTED', 'quiescence_proof': proof}, rec['revision'])
        MissionLedger(self.store).release_inference(rec['job_id'], proof=proof)
        return self._write({**rec, 'resource_lease': 'RELEASED'}, rec['revision'])

    def pending(self) -> list[dict]:
        with self.store.tx() as c:
            rows = [json.loads(r[0]) for r in c.execute('SELECT record FROM afo_execution_liveness')]
        return [r for r in rows if r['resource_lease'] == 'HELD']
