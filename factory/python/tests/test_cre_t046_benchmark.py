"""CRE-T046 (CRE-FR-013, plan section 7 categories 2 and 5): UART interrupt-boundary fixture, its injected race, and
an end-to-end SWE.1-6 + packager replay are frozen golden benchmark cases with known results."""
import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.reliability import benchmark as BM
from forge_factory.reliability.reproduce import WorktreePool


@pytest.fixture(scope="module")
def results():
    with WorktreePool(REPO_ROOT) as pool:
        rec = BM.run_suite("golden", "HEAD", pool)
    return {r["case_id"]: r for r in rec["results"]}


def test_suite_frozen_with_the_new_cases():
    suite = BM.load_suite("golden", BM.SUITES["golden"])
    ids = [c["case"]["case_id"] for c in suite["cases"]]
    assert {"BC-006", "BC-007", "BC-008", "BC-009"} <= set(ids)
    assert all(BM.check_case(c, BM.SUITES["golden"].parent, REPO_ROOT) is None for c in suite["cases"])


@pytest.mark.parametrize("case", ["BC-006", "BC-007", "BC-008", "BC-009"])
def test_new_cases_reproduce_their_known_result(results, case):
    assert results[case]["status"] == "PASS", results[case]
