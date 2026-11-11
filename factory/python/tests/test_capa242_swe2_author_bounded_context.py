"""CAPA-242 (owner lane 2026-11-11 SWE.2 stage, SPI LL L41E/L41F/L41G): every SWE.2 author session was refused
CAPABILITY_LIMIT before any model call ("complete serialized request 125345+147456 exceeds qualified context allowance
262144"). The native author's output cap is 16384 + the profile's 131072 thinking reserve, so its conversation must stay
under about 114,688 input tokens. The prompt told it to read the whole .forge-run/manifest.json (42 kB, 15 kB of it the
resume identity) and gave no bounded way into the delivered ST header (121 kB for SPI): it read the header in full and
again in parts and passed the bound before writing anything.
The factory now writes .forge-run/delivery/api-index.md (every in-scope delivered function: signature and the line range
of its comment and body) and .forge-run/delivery/swe2-brief.json (the manifest without its resume identity) when the code
is injected, and the brownfield SWE.2 author prompt reads those instead. Gates, limits and the pinned profile are unchanged."""
import json

from forge_factory.brownfield import api_index as A
from forge_factory.workflow import prompts as P

HDR = """/* header */
#ifndef X_H
#define X_H

/**
  * @brief  Enable SPI peripheral
  * @rmtoll CR1          SPE           LL_SPI_Enable
  * @param  SPIx SPI Instance
  * @retval None
  */
__STATIC_INLINE void LL_SPI_Enable(SPI_TypeDef *SPIx)
{
  SET_BIT(SPIx->CR1, SPI_CR1_SPE);
}

/**
  * @brief  Check if SPI peripheral is enabled
  */
__STATIC_INLINE uint32_t LL_SPI_IsEnabled(const SPI_TypeDef *SPIx)
{
  return ((READ_BIT(SPIx->CR1, SPI_CR1_SPE) == (SPI_CR1_SPE)) ? 1UL : 0UL);
}

__STATIC_INLINE void LL_SPI_Unused(SPI_TypeDef *SPIx)
{
  (void)SPIx;
}
#endif
"""


def _ws(tmp_path):
    ws = tmp_path / "ws"
    (ws / "software/ll").mkdir(parents=True)
    (ws / ".forge-run/delivery").mkdir(parents=True)
    (ws / "software/ll/x.h").write_text(HDR)
    (ws / ".forge-run/delivery/scope.json").write_text(json.dumps({"functions": [
        {"name": "LL_SPI_Enable", "file": "software/ll/x.h", "line": 11, "kind": "static_inline"},
        {"name": "LL_SPI_IsEnabled", "file": "software/ll/x.h", "line": 19, "kind": "static_inline"}]}))
    man = {"work_order": "WO-X", "delivery": {"code_mode": "FROZEN"}, "delivered": [{"path": "software/ll/x.h"}],
           "scope": {"x": 1}, "resume_identity": {"big": "y" * 5000}}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(man, indent=2))
    return ws, man


def test_index_lists_each_scope_function_with_exact_line_ranges(tmp_path):
    ws, man = _ws(tmp_path)
    A.write(ws, man)
    text = (ws / A.INDEX).read_text()
    lines = HDR.splitlines()
    assert "LL_SPI_Unused" not in text  # outside the work-order scope
    assert "| LL_SPI_Enable | `__STATIC_INLINE void LL_SPI_Enable(SPI_TypeDef *SPIx)` | software/ll/x.h | 5-14 |" in text
    assert "| LL_SPI_IsEnabled | `__STATIC_INLINE uint32_t LL_SPI_IsEnabled(const SPI_TypeDef *SPIx)` | software/ll/x.h | 16-22 |" in text
    assert lines[4].strip() == "/**" and lines[13] == "}" and lines[15].strip() == "/**" and lines[21] == "}"


def test_brief_is_the_manifest_without_the_resume_identity(tmp_path):
    ws, man = _ws(tmp_path)
    A.write(ws, man)
    brief = json.loads((ws / A.BRIEF).read_text())
    assert brief == {k: v for k, v in man.items() if k != "resume_identity"}
    assert len((ws / A.BRIEF).read_bytes()) < len((ws / ".forge-run/manifest.json").read_bytes()) / 4


def test_index_survives_a_missing_scope_file(tmp_path):
    ws, man = _ws(tmp_path)
    (ws / ".forge-run/delivery/scope.json").unlink()
    A.write(ws, man)
    assert "no in-scope delivered function" in (ws / A.INDEX).read_text()


def test_brownfield_swe2_author_reads_the_brief_and_the_index_not_the_whole_header(monkeypatch):
    monkeypatch.setitem(P.BROWNFIELD, "mode", "FROZEN")
    text = P.author_prompt("SWE.2")
    assert "read_file .forge-run/manifest.json." not in text
    assert "read_file .forge-run/delivery/swe2-brief.json" in text
    assert ".forge-run/delivery/api-index.md" in text and "never read a whole delivered file" in text


def test_other_phases_and_greenfield_swe2_keep_their_prompts(monkeypatch):
    monkeypatch.setitem(P.BROWNFIELD, "mode", None)
    assert "read_file .forge-run/manifest.json." in P.author_prompt("SWE.2")
    assert "api-index" not in P.author_prompt("SWE.2")
    monkeypatch.setitem(P.BROWNFIELD, "mode", "FROZEN")
    for ph in ("SWE.5", "SWE.6"):
        t = P.author_prompt(ph)
        assert "read_file .forge-run/manifest.json." in t and "api-index" not in t
