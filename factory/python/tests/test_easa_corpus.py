"""EASA-T066/T067: correct-versus-defective corpus on a copy of sealed r102 (detection and false positives)."""
import pytest
from forge_factory.assurance import corpus, oracle_gen
from forge_factory.common import data_root, sha256_file, state_dir

R102 = data_root() / "archives/WO-0002B-STM32N6-RCC-HAL-r102/forge-c-WO-0002B-STM32N6-RCC-HAL-r102-review.zip"
INPUTS = state_dir() / "workorders/WO-0002A-STM32N6-RCC-LL-r108/workspace/inputs"


@pytest.mark.skipif(not (R102.is_file() and (INPUTS / "sections").is_dir()), reason="sealed archive/RM inputs absent")
def test_t066_corpus_detection_and_no_false_positives():
    h = sha256_file(R102)
    r = corpus.run(R102, INPUTS)
    s = r["summary"]
    assert s["variants"] == 10 and s["neither"] == [] and s["easa_caught"] == 10 and s["factory_caught"] == 8
    assert set(s["easa_only"]) == {"D01", "D05"}                     # wrong generated bit, off-by-one poll bound
    assert r["false_positives_on_correct"] == {"factory": []}         # nothing reported on the unmodified copy
    assert sha256_file(R102) == h


def test_selected_bit_requirement_uses_api_contract_and_rm():
    from tests_easa_rm import idx_from  # noqa: F401  (only the synthetic sections are needed)

    reqs = "- **SWR-007** When a peripheral clock enable is requested for a valid selector, the RCC driver shall set " \
           "the selected enable bit of RCC_CR.\n"
    arch = "| SWR-007 | HAL_RCC_HSI_Enable, HAL_RCC_FOO_Enable |\n"
    hdr = "hal_status_t HAL_RCC_HSI_Enable(void);\nhal_status_t HAL_RCC_FOO_Enable(void);\n"
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        idx = idx_from(Path(td))
    idx["RCC_CR"]["fields"]["HSIEN"] = idx["RCC_CR"]["fields"]["HSION"]
    cases, notes = oracle_gen.derive(reqs, arch, hdr, idx)
    assert [(c["function"], c["field"], c["mask"]) for c in cases] == [("HAL_RCC_HSI_Enable", "HSIEN", 8)]
    assert notes == ["ORACLE_NOT_DERIVABLE:SWR-007:FOOEN not a field of RCC_CR"]
