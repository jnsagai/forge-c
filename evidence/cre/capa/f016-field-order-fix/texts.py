import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from forge_factory.onboarding import facts, texts
root = Path(__file__).parent
package = json.loads((root / "package.json").read_text())
owner = json.loads((root / "owner.json").read_text())
context = SimpleNamespace(spec=owner, delivery=owner["delivery"])
api = facts.value(package, "api")
api["prototypes"] = {name: api["prototypes"][name] for name in owner["delivery"]["scope"]["functions"]}
macros = {f"{reg}_{field}" for reg, entry in facts.value(package, "register_index").items() for field in entry["fields"]}
with patch.object(texts, "device_macros", lambda ctx: macros):
    live = texts.generate(context, package)
    saved = texts.generate(context, json.loads(json.dumps(package, sort_keys=True)))
if live != saved:
    print("SYMPTOM_PRESENT:saved package facts change generated function order")
    raise SystemExit(1)
print("SYMPTOM_ABSENT")
