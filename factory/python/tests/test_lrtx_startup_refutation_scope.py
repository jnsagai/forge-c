"""A startup invariant cannot refute a distinct register-reset specification finding."""
import json

import pytest

from forge_factory.lrtx import review


@pytest.fixture
def frozen_requirements(tmp_path):
    (tmp_path / '.forge-run').mkdir()
    (tmp_path / '.forge-run/manifest.json').write_text(json.dumps({'target': {}}))
    path = tmp_path / 'workproducts/SWE.1/software_requirements.md'
    path.parent.mkdir(parents=True)
    path.write_text('\n'.join(
        f'- **SWR-{number:03d}** The test driver shall preserve unrelated register bits.\n'
        '  - Source: synthetic fixture\n  - Verification: Pass when unrelated bits are unchanged.\n'
        for number in (25, 26, 27, 28, 30)
    ) + '- **SWR-029** While no LL function has been called after reset, the test driver shall not write any register.\n'
        '  - Source: synthetic fixture\n  - Verification: Pass when no write occurs.\n')
    return tmp_path


@pytest.mark.parametrize('finding', [
    'The source section does not document CONTROL_RSTR reset bits, but SWR-025 requires asserting them.',
    'The requirements do not specify reset register values for CONTROL_RSTR.',
    'There are no reset bit definitions for CONTROL_RSTR in the cited source.',
    'The reset register semantics are not specified for CONTROL_RSTR.',
    'workproducts/SWE.1/software_requirements.md Open points is inconsistent with SWR-025 through SWR-028 '
    'in the same file: it states that the supplied source section does not document RCC_AHB1RSTR reset bits '
    'and that only RCC_AHB1ENR no-write behaviour is specified, while SWR-025 through SWR-028 require '
    'set/clear of RCC_AHB1RSTR.ADC12RST and RCC_AHB1RSTR.GPDMA1RST.',
])
def test_startup_invariant_does_not_refute_register_reset_findings(frozen_requirements, finding):
    assert review.fact_conflicts(frozen_requirements, 'SWE.1', 'SWE1-02', [finding]) == []
    verdict = {'verdict': 'FAIL', 'findings': [finding],
               'evidence_checked': ['workproducts/SWE.1/software_requirements.md']}
    assert review.validate_verdict(verdict, set(verdict['evidence_checked']),
                                   frozen_requirements, 'SWE.1', 'SWE1-02') == []
    assert verdict['verdict'] == 'FAIL' and verdict['findings'] == [finding]


@pytest.mark.parametrize('finding', [
    'The software requirements do not specify failure handling, reset/startup behavior or safe states.',
    'The requirements have no startup behaviour.',
    'Reset behaviour is not specified.',
    'The startup behavior is missing.',
])
def test_explicit_denial_of_present_startup_behaviour_is_still_refuted(frozen_requirements, finding):
    found = review.fact_conflicts(frozen_requirements, 'SWE.1', 'SWE1-02', [finding])
    assert len(found) == 1 and 'SWR-029 specifies it' in found[0]
