"""SC-001 preparation audit: regenerate texts while tracing reads; never inspect model reasoning or modify inputs."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import yaml
from forge_factory.benchmark.queue import load
from forge_factory.common import REPO_ROOT, sha256_file
from forge_factory.onboarding import facts, identity, onboarding_dir
from forge_factory.onboarding.texts import generate

BASE = "11482e3"
reads = set()
original = Path.read_text


def traced(path, *args, **kwargs):
    reads.add(path.resolve())
    return original(path, *args, **kwargs)


for item in load(REPO_ROOT / "config/factory/benchmark/st-driver-onboarding-queue.yaml")["items"]:
    example = REPO_ROOT / item["example"]
    owner = json.loads((example / "workorder.json").read_text())
    old = REPO_ROOT / "examples" / example.name.replace("e-st-", "d-st-").removesuffix("-ob")
    legacy_scope = json.loads((old / "workorder.json").read_text())["scope"]
    assert not {"files", "dependencies", "configure"} & owner["delivery"].keys()
    package = facts.read_package(onboarding_dir(example.name))
    assert facts.canonical_hash(package) == package["sha256"]
    assert "; ".join(owner["scope"]) in package["texts"]["prompt"]["swe1_cover"]["text"]
    tracked = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "HEAD", "--", item["example"]],
                                      cwd=REPO_ROOT, text=True).splitlines()
    assert tracked == [item["example"] + "/workorder.json"], tracked
    reads.clear()
    with patch.object(Path, "read_text", traced):
        context = identity.context(example)
        regenerated = generate(context, package)
    assert json.loads(json.dumps(regenerated)) == package["texts"], example.name
    assert not any("config/factory/peripherals/" in str(path) for path in reads), sorted(reads)
    print(json.dumps({"key": example.name, "sha256": package["sha256"], "scope_matches_owner_input": True,
                      "scope_verbatim_from_legacy": owner["scope"] == legacy_scope,
                      "scope_note": "The acceptance scope simplifies the legacy scope's hand-derived details; "
                                    "the exact acceptance scope is included in the signed package text.",
                      "example_contains_only_owner_workorder": True, "generated_texts_identical": True,
                      "hand_profile_reads": 0, "reads": [{"path": str(path), "sha256": sha256_file(path)}
                                                          for path in sorted(reads)]}))
changes = subprocess.check_output(["git", "diff", "--name-status", BASE, "HEAD", "--", "config/factory/peripherals"],
                                  cwd=REPO_ROOT, text=True).strip()
print("Legacy profile changes since baseline (reported, never used to generate these packages):", changes or "none")
assert changes == "M\tconfig/factory/peripherals/gpio.yaml", changes
old_profile = yaml.safe_load(subprocess.check_output(["git", "show", f"{BASE}:config/factory/peripherals/gpio.yaml"],
                                                    cwd=REPO_ROOT, text=True))
new_profile = yaml.safe_load((REPO_ROOT / "config/factory/peripherals/gpio.yaml").read_text())
old_description = old_profile["prompt"].pop("target_model")
new_description = new_profile["prompt"].pop("target_model")
assert old_profile == new_profile
assert new_description == old_description.replace("the others 0", "GPIO_SECCFGR and GPIO_PRIVCFGR 0x0000FFFF, the others 0")
print("PASS SC-001 preparation: four owner-only examples, exact acceptance scope binding, "
      "identical texts, zero hand-profile reads.")
print("The legacy GPIO model-reset description correction is reported explicitly; it is not an input of these packages.")
