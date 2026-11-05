"""Actual public host tools on normally approved macro corrections; no product-phase or model qualification."""
import json
import shutil
from types import SimpleNamespace

import pytest
import test_unit_target_carry as F
from forge_factory import rework_context as R
from forge_factory import workorder as W
from forge_factory.common import sha256_file
from forge_factory.inspection import defects
from forge_factory.inspection import provided_changes as PC
from forge_factory.inspection.engine import Store
from forge_factory.mcp import sdk
from forge_factory.policy.authz import Authorizer, Binding
from forge_factory.workflow import ll_fake
from forge_factory.workflow import provided_input_identity as I
from forge_factory.workflow import provided_ll_unit as P
from forge_factory.workflow import unit_target_observation as O
from test_provided_effective_identity import LL, execute
from test_unit_target_observation import write


@pytest.fixture
def reviewed_macro(tmp_path, monkeypatch):
    original = F.observation_ws

    def origin(ws):
        original.__wrapped__(ws)
        vendor = ws / 'inputs/vendor/include/stm32n6xx.h'
        vendor.write_text(vendor.read_text() + '\n#define __STATIC_INLINE static inline\n')
        p = ws / LL
        p.write_text(p.read_text().replace('static inline void',
            '#define LL_WWDG_CLEAR_VALUE 1U - 1U\n__STATIC_INLINE void')
            .replace('x->SR = 0U', 'x->SR = 2U * LL_WWDG_CLEAR_VALUE'))
        man = json.loads((ws / '.forge-run/manifest.json').read_text())
        man.update(unit_verification='uspec-gtest-v1', hal_unit_isolation='ll-fake-v1')
        write(ws, '.forge-run/manifest.json', man)

    class BeforeUnit(Exception):
        pass

    def stop(*a, **kw):
        raise BeforeUnit()

    with monkeypatch.context() as boot:
        boot.setattr(F, 'observation_ws', SimpleNamespace(__wrapped__=origin))
        boot.setattr(sdk, 'invoke', stop)
        with pytest.raises(BeforeUnit):
            F.passed.__wrapped__(tmp_path, monkeypatch)
    ws = tmp_path / 'state/workorders/WO-CONTROL-SOURCE/workspace'
    PC.save_original(ws, LL, (ws / LL).read_bytes())
    (ws / O.DECLARATION).unlink()
    (ws / 'software/tests/unit/test_control.c').unlink()
    write(ws, 'software/tests/unit/test_reviewed.cpp', P.MARKER + '''
#include <gtest/gtest.h>
extern "C" {
#include "stm32n6xx_hal_wwdg.h"
}
TEST(ReviewedLL, UT_099) {
 WWDG->SR=1U; EXPECT_EQ(HAL_WWDG_ClearEarlyWakeupFlag(),HAL_OK); EXPECT_EQ(WWDG->SR,0U);
}
''')
    assert ll_fake.write(ws)
    fake = ws / ll_fake.fake_header(ws)
    original_fake = fake.read_bytes()
    # An actual intact prefix supplies the original approved input for a later failed-SWE3 retry.
    prefix = ws.parent.parent / 'WO-CONTROL-PASSED2/workspace'
    shutil.copytree(ws, prefix)
    prior = json.loads((prefix / '.forge-run/manifest.json').read_text())
    prior['work_order'] = 'WO-CONTROL-PASSED2'
    write(prefix, '.forge-run/manifest.json', prior)
    assert execute(ws, monkeypatch)['status'] == 'FAIL'  # genuine precedence defect leaves SR nonzero
    defect = defects.report(ws, detected_phase='SWE.4', reported_by='swe4-author', kind='CODE',
        summary='CONTROL UT-099 USPEC-HAL-04-03: ' + LL + ' macro precedence leaves the flag set.',
        requirement_ids=['SWR-033'], test_files=[], evidence_refs=[LL + ':3'],
        requirement_quote='When clearing is requested, the WWDG driver shall clear its early wakeup flag.')
    assert defects.take_upstream(ws, 'SWE.3')[0]['id'] == defect['id']
    author = Authorizer(Binding('CONTROL', str(ws), {'a': {'role': 'swe3-author', 'phase': 'SWE.3'}}))
    assert author.decide('a', 'write_file', {'path': LL, 'content': 'CONTROL'}).allow
    p = ws / LL
    p.write_text(p.read_text().replace('#define LL_WWDG_CLEAR_VALUE 1U - 1U',
                                      '#define LL_WWDG_CLEAR_VALUE (1U - 1U)'))
    assert PC.findings(ws) == []
    F.pass_control(Store(ws), 'SWE.3')
    assert defects.mark_fixed(ws, 'SWE.3', Store(ws).latest_baseline('SWE.3')['baseline_id']) == [defect['id']]
    assert I.effective_identity(ws, LL)['approval']
    assert fake.read_bytes() == original_fake and not ll_fake.modified(ws)
    return ws, original_fake


def test_reviewed_macro_real_ll_suite_checks_the_unchanged_original_fake(reviewed_macro, monkeypatch):
    ws, original = reviewed_macro
    result = execute(ws, monkeypatch)
    assert result['status'] == 'PASS', result
    assert (ws / ll_fake.fake_header(ws)).read_bytes() == original


@pytest.mark.parametrize('history', [False, True])
def test_default_and_history_builds_use_effective_macro_without_changing_original(reviewed_macro, monkeypatch, history):
    ws, original = reviewed_macro
    marker = '// FORGE_UNIT_BACKEND: ll-call-arguments-v1\n' if history else ''
    write(ws, 'software/tests/unit/test_effective.cpp', marker + '''#include <gtest/gtest.h>
extern "C" {
#include "stm32n6xx_hal_wwdg.h"
}
TEST(ReviewedLL, UT_100) {
 ll_fake_reset(); EXPECT_EQ(2U * LL_WWDG_CLEAR_VALUE,0U);
 EXPECT_EQ(HAL_WWDG_ClearEarlyWakeupFlag(),HAL_OK);
 EXPECT_EQ(ll_fake_calls(LL_FAKE_LL_WWDG_ClearFlag_EWKUP),1U);
}
''')
    # Keep the original failing real-LL test unchanged and execute both backends; no discarded predicate.
    result = execute(ws, monkeypatch)
    assert result['status'] == 'PASS', result
    assert (ws / ll_fake.fake_header(ws)).read_bytes() == original
    suffix = '.ll-call-arguments' if history else '.ll-effective-fake'
    binding = json.loads((ws / ('build/tests-unit/test_effective' + suffix + '/binding.json')).read_text())
    identity = binding['provided_effective_identity']
    if history:
        identity = identity[0]
    assert identity['effective_sha256'] == sha256_file(ws / LL) and identity['approval']
    assert binding['original_fake_sha256'] == sha256_file(ws / ll_fake.fake_header(ws))
    assert binding['target_or_register_effect_claim'] is False


@pytest.mark.parametrize('replacement', ['comment', 'effective'])
def test_modified_original_fake_is_still_refused_after_real_approval(reviewed_macro, monkeypatch, replacement):
    ws, original = reviewed_macro
    fake = ws / ll_fake.fake_header(ws)
    fake.chmod(0o644)
    fake.write_text(original.decode() + '\n/* changed */\n' if replacement == 'comment'
                    else ll_fake.generate((ws / LL).read_text(), 'll_wwdg_regs'))
    result = execute(ws, monkeypatch)
    assert result['status'] == 'FAIL' and any('GENERATED_TEST_DOUBLE_MODIFIED' in x for x in result['issues']), result



def test_public_c_harness_uses_private_effective_includes(reviewed_macro, monkeypatch):
    ws, original = reviewed_macro
    write(ws, 'software/tests/unit/test_effective.c', '''#include <stdio.h>
#define LL_FAKE_IMPLEMENTATION
#include "stm32n6xx_hal_wwdg.h"
int main(void) {
 if (2U * LL_WWDG_CLEAR_VALUE != 0U) { puts("UT-101 FAIL"); return 1; }
 ll_fake_reset();
 if (HAL_WWDG_ClearEarlyWakeupFlag() != HAL_OK ||
     ll_fake_calls(LL_FAKE_LL_WWDG_ClearFlag_EWKUP) != 1U) { puts("UT-101 FAIL"); return 2; }
 puts("UT-101 PASS"); return 0;
}
''')
    result = execute(ws, monkeypatch)
    assert result['status'] == 'PASS', result
    binding = ws / 'build/tests-unit/test_effective.ll-effective-fake/binding.json'
    assert binding.is_file() and (ws / ll_fake.fake_header(ws)).read_bytes() == original


def terminal_source(monkeypatch, source, phase):
    man = json.loads((source / '.forge-run/manifest.json').read_text())
    man['phase_scope'] = {'stop_after': phase}
    write(source, '.forge-run/manifest.json', man)
    write(source, '.forge-run/fabro_run_id', 'CONTROL-RUN')
    write(source, '.forge-run/gates/gate-log.jsonl', json.dumps({'phase': phase, 'step': 'author',
          'result': 'REJECTED', 'status': 'BLOCKED', 'issues': ['CONTROL failed authorship remains reference data.']})+'\n')

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def get_run(self, _):
            return {'id': 'CONTROL-RUN', 'source_directory': str(source),
                    'lifecycle': {'status': {'kind': 'succeeded', 'reason': 'completed'}}}
    monkeypatch.setattr(R, 'client_for_workspace', lambda _: Client())
    latest = sorted((source / 'inspection' / phase).glob('INS-*.json'))
    return {'source_work_order': 'WO-CONTROL-SOURCE', 'phase': phase,
            'inspection_sha256': sha256_file(latest[-1]) if latest else 'ABSENT',
            'gate_log_sha256': sha256_file(source / '.forge-run/gates/gate-log.jsonl')}


def test_whole_normal_retry_context_preserves_exact_approved_correction(reviewed_macro, monkeypatch):
    source, _ = reviewed_macro
    request = terminal_source(monkeypatch, source, 'SWE.4')
    destination, man = F.destination(source, 'WO-CONTROL-RETRY4')
    assert W.resume_from(destination, man, 'WO-CONTROL-SOURCE', upto='SWE.4')[0] == 'SWE.4'
    doc = R.prepare(destination, man, request, 'SWE.4')
    row = doc['provided_input_states'][0]
    assert row['source_state'] == 'SAME_INDEPENDENTLY_REVIEWED_CORRECTION'
    assert row['destination_identity'] == I.effective_identity(source, LL)
    assert row['inherited_verdict'] is False
    assert sha256_file(source / LL) == sha256_file(destination / LL)
    # A restored original cannot silently replace the reviewed LL variant of the carried SWE.3 approval.
    item = json.loads((source / '.forge-run/manifest.json').read_text())['provided'][0]
    (destination / LL).chmod(0o644)
    (destination / LL).write_bytes(I._original(source, item))
    with pytest.raises(R.ReworkRefused):
        R.prepare(destination, man, request, 'SWE.4')


def test_failed_swe3_correction_is_bound_as_data_with_original_destination(reviewed_macro, monkeypatch):
    source, _ = reviewed_macro
    new = defects.report(source, detected_phase='SWE.4', reported_by='swe4-author', kind='CODE',
        summary='CONTROL next incomplete correction: ' + LL + ' still needs flag-clear verification.',
        requirement_ids=['SWR-033'], test_files=[], evidence_refs=[LL + ':3'],
        requirement_quote='When clearing is requested, the WWDG driver shall clear its early wakeup flag.')
    assert defects.take_upstream(source, 'SWE.3')[0]['id'] == new['id']
    path = source / LL
    path.write_text(path.read_text().replace('(1U - 1U)', '(1U - 0U)'))
    assert PC.findings(source) == []
    store = Store(source)
    baseline = store.freeze('SWE.3', 'swe3-author')
    failed = F._all_pass('SWE.3')
    failed['SWE3-02'] = {'verdict': 'FAIL', 'findings': ['CONTROL incomplete macro correction remains wrong.'],
                         'evidence_refs': [LL]}
    review = store.record_inspection('SWE.3', 'swe3-inspector', baseline['baseline_id'], failed)
    assert review['verdict'] == 'FAIL'
    request = terminal_source(monkeypatch, source, 'SWE.3')
    destination, man = F.destination(source, 'WO-CONTROL-RETRY3')
    pristine = I._original(source, json.loads((source / '.forge-run/manifest.json').read_text())['provided'][0])
    (destination / LL).write_bytes(pristine)
    assert W.resume_from(destination, man, 'WO-CONTROL-PASSED2', upto='SWE.3')[0] == 'SWE.3'
    assert Store(source).gate('SWE.3')['decision'] != 'PASS'
    doc = R.prepare(destination, man, request, 'SWE.3')
    row = doc['provided_input_states'][0]
    assert row['source_state'] == 'IN_PROGRESS_REFERENCE_ONLY_NOT_CARRIED_OR_APPROVED'
    assert row['destination_identity']['approval'] is None and row['inherited_verdict'] is False
    assert row['source_change_reference']['code_defect_sha256']
    assert (destination / LL).read_bytes() == pristine
    assert sha256_file(source / LL) != sha256_file(destination / LL)
