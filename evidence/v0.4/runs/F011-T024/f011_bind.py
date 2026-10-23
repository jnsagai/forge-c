"""Write the role binding a work-order run would write (workorder.run: build -> binding_for), for an author-only
trial start workspace prepared with --intake-only. Same factory functions and arguments as workorder.run."""
import json
import sys
from pathlib import Path

from forge_factory.layer import HAL_UNIT_ISOLATION, TRACE_PROFILE
from forge_factory.workflow.builder import binding_for, build
from forge_factory.workorder import local_profile_structured

ws = Path(sys.argv[1]).resolve()
m = json.loads((ws / ".forge-run/manifest.json").read_text())
secmap = {}
for line in (ws / "inputs/index.md").read_text().splitlines():
    parts = [x.strip() for x in line.split(" | ")]
    if len(parts) == 4 and parts[0][:1].isdigit() and parts[0] not in secmap:
        secmap[parts[0]] = parts[3]
graph, nodes = build(m["work_order"], goal=f"{m['driver']} for {m['target'].get('part_number')} (offline review)",
                     sections=secmap, chunk_lines=40, layer=m.get("layer", "LL+HAL"),
                     trace=m.get("trace_profile") == TRACE_PROFILE,
                     isolation=m.get("hal_unit_isolation") == HAL_UNIT_ISOLATION,
                     brownfield=m.get("code_mode") if m.get("delivery") else None, peripheral=m.get("peripheral"),
                     delivery_style=((m.get("delivery") or {}).get("build") or {}).get("style"),
                     structured=local_profile_structured(m["local_profile"], m, sys.argv[2]))
binding_for(m["work_order"], str(ws), nodes).dump(ws / ".forge-run/binding.json")
print(json.dumps({"binding": str(ws / ".forge-run/binding.json"), "nodes": len(nodes)}))
