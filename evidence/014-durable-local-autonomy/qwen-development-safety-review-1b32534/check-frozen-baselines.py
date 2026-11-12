"""Reproduce fixed-policy facts; never execute model-proposed test strings."""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
sys.path.insert(0, str(REPO / "factory/python"))
from forge_factory.release import development as D  # noqa: E402


def verify(work_dir):
    rows = []
    with tempfile.TemporaryDirectory(dir=work_dir) as temporary:
        root = Path(temporary)
        ws, stage = root / "ws", root / "stage"
        (ws / ".forge-run").mkdir(parents=True)
        manifest = {"purpose": "DEVELOPMENT", "development_safety": D.binding("DEVELOPMENT")}
        (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
        for rel in D.BASES:
            base = REPO / rel
            before = hashlib.sha256(base.read_bytes()).hexdigest()
            original = json.loads(base.read_text())
            assert D.SNAPSHOT not in original["required_files"] and D.DEFERRALS not in original["required_files"]
            path = D.effective_policy(base, ws, stage)
            first = path.read_bytes()
            effective = json.loads(first)
            assert D.effective_policy(base, ws, stage).read_bytes() == first
            assert effective["required_files"].count(D.SNAPSHOT) == effective["required_files"].count(D.DEFERRALS) == 1
            assert effective["schema"] == original["schema"] + "-development"
            assert hashlib.sha256(base.read_bytes()).hexdigest() == before
            rows.append({"base": rel, "sha256": before, "source_schema": original["schema"],
                         "effective_schema": effective["schema"], "repeated_same_base_is_idempotent": True,
                         "metadata_required_once": True, "base_unchanged": True})
    recorded = json.loads((ROOT / "independent-check.json").read_text())
    assert rows == recorded["actual_baselines"]
    return {"status": "PASS_FIXED_BASELINE_FACTS", "baselines": len(rows),
            "supported_model_findings": 0, "new_model_requests": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    print(json.dumps(verify(parser.parse_args().work_dir), sort_keys=True))
