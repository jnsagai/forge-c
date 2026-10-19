"""AFO-T072 (AT-065/066): the acceptance report derives each AT verdict from the evidence status of the tasks that
cite it - never from tasks.md boxes - and reports BLOCKED/PARTIAL/NOT_RUN honestly."""
from forge_factory.afo import acceptance, status


def test_at_verdicts_follow_task_evidence(monkeypatch):
    real = status.report()
    tasks = {k: {**v, "status": "PASS"} for k, v in real["tasks"].items()}
    monkeypatch.setattr(status, "report", lambda: {**real, "tasks": tasks})
    r = acceptance.report()
    assert len(r["acceptance"]) == 66 and r["counts"]["PASS"] == 66                     # every AT is cited by a task
    some = next(x for x in r["acceptance"] if len(x["tasks"]) >= 2)
    t1, t2 = list(some["tasks"])[:2]
    for st, want in (("BLOCKED", "BLOCKED"), ("PARTIAL", "PARTIAL"), ("NOT_RUN", "PARTIAL")):
        tasks2 = {**tasks, t1: {**tasks[t1], "status": st}}
        monkeypatch.setattr(status, "report", lambda t=tasks2: {**real, "tasks": t})
        assert next(x for x in acceptance.report()["acceptance"] if x["at"] == some["at"])["verdict"] == want
    none = {k: {**v, "status": "NOT_RUN"} for k, v in tasks.items()}
    monkeypatch.setattr(status, "report", lambda: {**real, "tasks": none})
    assert acceptance.report()["counts"]["NOT_RUN"] == 66
    assert "no compliance" in r["statement"] and t2


def test_generated_documents_match_the_generator():
    r = acceptance.report()
    assert acceptance.markdown(r).startswith("# Feature 005 (AFO) acceptance report")
