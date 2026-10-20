"""CAPA-059 (b006): a reset/startup invariant mapped to a host unit test is a SWE.1 gate finding (the host harness starts
after reset; b006 UT-018 was tautological and SWE.4 ran out of rework budget). Mapped to the Robot suite it passes."""
from forge_factory.inspection.test_mapping import startup_on_host
from forge_factory.workflow import prompts as P

REQ = ("# Software requirements\n- **SWR-018** While no LL function has been called after reset, the RCC LL driver shall "
       "not write any RCC register.\n- **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION.\n")


def _ws(tmp_path, rows):
    (tmp_path / "workproducts/SWE.1").mkdir(parents=True)
    (tmp_path / "traceability").mkdir()
    (tmp_path / "workproducts/SWE.1/software_requirements.md").write_text(REQ)
    (tmp_path / "traceability/requirements_to_tests.csv").write_text("requirement_id,test_id,test_file\n" + rows)
    return tmp_path


def test_capa059_startup_invariant_on_host_test_is_a_finding(tmp_path):
    ws = _ws(tmp_path, "SWR-018,UT-018,software/tests/unit/test_rcc.c\nSWR-001,UT-001,software/tests/unit/test_rcc.c\n")
    f = startup_on_host(ws)
    assert len(f) == 1 and f[0].startswith("SWE1:STARTUP_INVARIANT_ON_HOST_TEST:SWR-018")
    assert "software/tests/software/test_rcc_requirements.robot" in f[0]


def test_capa059_startup_invariant_on_robot_passes(tmp_path):
    ws = _ws(tmp_path, "SWR-018,SWR-018,software/tests/software/test_rcc_requirements.robot\n"
                       "SWR-001,UT-001,software/tests/unit/test_rcc.c\n")
    assert startup_on_host(ws) == []


def test_capa059_swe1_prompt_names_the_rule():
    assert "reset/startup ('While no ... after reset') requirements test_id = the SWR" in " ".join(P.AUTHOR_STEPS["SWE.1"])
