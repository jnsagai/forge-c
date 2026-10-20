"""CAPA-056 (b006 DEF-001): delivered code is frozen input - the target build of a delivery compiles without -Werror
(warnings recorded as issues) and vendor/host-device headers are system headers; factory code keeps -Werror."""
import json

from forge_factory.brownfield import cmsis
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import build as B

VENDOR = "#include <stdint.h>\nstatic inline uint32_t vendor_conv(int32_t v) { return v; }\n"


def _ws(tmp_path, delivered: bool):
    (tmp_path / ".forge-run/delivery").mkdir(parents=True)
    (tmp_path / "inputs/vendor/include").mkdir(parents=True)
    (tmp_path / "software/ll").mkdir(parents=True)
    (tmp_path / "software/src").mkdir(parents=True)
    (tmp_path / "inputs/vendor/include/vendor_dev.h").write_text(VENDOR)
    (tmp_path / "software/ll/ll_x.h").write_text(
        '#include "vendor_dev.h"\nstatic inline unsigned short LL_X_Get(unsigned v) { return v; }\n')
    (tmp_path / ".forge-run/delivery/scope.json").write_text(json.dumps({"functions": [{"name": "LL_X_Get"}]}))
    m = {"layer": "LL"}
    if delivered:
        m.update(code_mode="FROZEN", delivered=[{"path": "software/ll/ll_x.h", "role": "delivered_code"}],
                 delivery={"code_mode": "FROZEN", "build": {"style": "cmsis", "defines": [], "secure": False}})
    else:
        (tmp_path / "software/src/x.c").write_text("unsigned short f(unsigned v);\nunsigned short f(unsigned v) { return v; }\n")
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps(m))
    return tmp_path


def test_capa056_delivery_warnings_are_recorded_not_fatal(tmp_path):
    ws = _ws(tmp_path, True)
    assert cmsis.target_flags(ws)[:2] == ["-isystem", str(ws / cmsis.VENDOR_DIR)]
    r = B.compile_(sdk.ToolContext("forge-build-mcp", "compile", "swe3-author", "SWE.3", ws, "r"),
                   B.CompileIn(profile="target-cm55-gcc"))
    assert r["status"] == "PASS", r
    assert any("conversion" in i and "ll_x.h" in i for i in r["issues"])  # the delivery's own warning, recorded
    assert not any("vendor_dev.h" in i for i in r["issues"])  # the vendor header's warning is a system header's


def test_capa056_factory_code_keeps_werror(tmp_path):
    ws = _ws(tmp_path, False)
    r = B.compile_(sdk.ToolContext("forge-build-mcp", "compile", "swe3-author", "SWE.3", ws, "r"),
                   B.CompileIn(profile="target-cm55-gcc"))
    assert r["status"] == "FAIL" and any("conversion" in i for i in r["issues"])
