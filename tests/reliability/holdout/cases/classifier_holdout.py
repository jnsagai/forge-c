"""Holdout: labelled failure texts never used to write the rules; routing safety + accuracy."""
import json
import sys
from pathlib import Path

from forge_factory.reliability.taxonomy import classify

cases = json.loads((Path(sys.argv[1]) / "ws/labels.json").read_text())
ok = sum(classify(c["text"]).failure_class == c["class"] for c in cases)
unsafe = sum(c["class"] == "PRODUCT_QUALITY" and classify(c["text"]).route != "SWE_REWORK" for c in cases)
print(json.dumps({"observed": {"n": len(cases), "correct": ok, "accuracy": round(ok / len(cases), 3),
                               "product_quality_routed_elsewhere": unsafe}}))
