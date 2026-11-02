"""CAPA-112 (RPR-112, runs WO-F014-CMP-SWE1-CRCL-20261102-05/-06): a FROZEN brownfield order's SWE.1 author and
inspector get the scoped functions' argument constants (names and values) as a declared input, never the code.

Before the fix the full ST CRC LL order (LL_CRC_SetPolynomialSize, LL_CRC_Set*DataReverseMode) was written without the
LL_CRC_POLYLENGTH_* / LL_CRC_*DATA_REVERSE_* constants, and the inspector failed SWE1-02 three times."""
from __future__ import annotations

import json

import pytest
from brownfield_fixtures import HEADER, SCOPE, example_copy
from forge_factory import workorder as WO
from forge_factory.brownfield import interface as BI
from forge_factory.common import sha256_file

# a delivered header in the ST style: doxygen @arg lists naming object-like macros built from a dependency's masks
DEP = "#define DEV_CR_SIZE_Pos (3U)\n#define DEV_CR_SIZE_Msk (0x3UL << DEV_CR_SIZE_Pos)\n" \
      "#define DEV_CR_SIZE_0 (0x1UL << DEV_CR_SIZE_Pos)\n#define DEV_CR_SIZE_1 (0x2UL << DEV_CR_SIZE_Pos)\n"
CODE = """\
#define LL_DEV_SIZE_32B   0x00000000U          /*!< comment text is never copied */
#define LL_DEV_SIZE_16B   DEV_CR_SIZE_0
#define LL_DEV_SIZE_7B    (DEV_CR_SIZE_1 | DEV_CR_SIZE_0)

/**
  * @brief  Set the size (this prose is never copied)
  * @param  DEVx Instance
  * @param  Size This parameter can be one of the following values:
  *         @arg @ref LL_DEV_SIZE_32B
  *         @arg @ref LL_DEV_SIZE_16B
  *         @arg @ref LL_DEV_SIZE_7B
  * @retval None
  */
__STATIC_INLINE void LL_DEV_SetSize(DEV_TypeDef *DEVx, uint32_t Size)
{
  MODIFY_REG(DEVx->CR, DEV_CR_SIZE_Msk, Size);
}

/**
  * @brief  Return the size
  * @param  DEVx Instance
  * @retval Returned value can be one of the following values:
  *         @arg @ref LL_DEV_SIZE_32B
  *         @arg @ref LL_DEV_SIZE_16B
  */
__STATIC_INLINE uint32_t LL_DEV_GetSize(DEV_TypeDef *DEVx)
{
  return (uint32_t)(READ_BIT(DEVx->CR, DEV_CR_SIZE_Msk));
}

/**
  * @brief  Write data
  * @param  DEVx Instance
  * @param  Data value between Min_Data=0 and Max_Data=0xFFFFFFFF
  * @retval None
  */
__STATIC_INLINE void LL_DEV_Write(DEV_TypeDef *DEVx, uint32_t Data)
{
  WRITE_REG(DEVx->DR, Data);
}
"""
FILES = {"software/ll/ll_dev.h": CODE.encode(), "inputs/vendor/include/dev.h": DEP.encode()}
RECS = [{"path": "software/ll/ll_dev.h", "role": "delivered_code"},
        {"path": "inputs/vendor/include/dev.h", "role": "delivered_dependency"}]


def test_extract_gives_argument_and_return_constants_with_values_only():
    doc = BI.extract(FILES, RECS, ["LL_DEV_SetSize", "LL_DEV_GetSize", "LL_DEV_Write", "LL_DEV_Missing"])
    by = {f["function"]: f for f in doc["functions"]}
    assert set(by) == {"LL_DEV_SetSize", "LL_DEV_GetSize"}  # a free-range value argument has no constants
    assert by["LL_DEV_SetSize"]["parameters"] == [{"name": "Size", "constants": [
        {"name": "LL_DEV_SIZE_32B", "value": "0x00000000"}, {"name": "LL_DEV_SIZE_16B", "value": "0x00000008"},
        {"name": "LL_DEV_SIZE_7B", "value": "0x00000018"}]}]
    assert by["LL_DEV_GetSize"]["returns"] == [{"name": "LL_DEV_SIZE_32B", "value": "0x00000000"},
                                               {"name": "LL_DEV_SIZE_16B", "value": "0x00000008"}]
    text = BI.render(doc).decode()
    for code_text in ("MODIFY_REG", "DEVx->", "never copied", "__STATIC_INLINE", "DEV_CR_SIZE_0"):
        assert code_text not in text  # FR-007: no body, declaration, comment or expression of the code
    assert BI.render(doc) == BI.render(BI.extract(FILES, RECS, ["LL_DEV_SetSize", "LL_DEV_GetSize"]))  # deterministic


def test_extract_ignores_names_that_are_not_delivered_constants_and_returns_none_without_any():
    assert BI.extract(FILES, RECS, ["LL_DEV_Write"]) is None
    other = CODE.replace("#define LL_DEV_SIZE_16B   DEV_CR_SIZE_0\n", "")
    doc = BI.extract({**FILES, "software/ll/ll_dev.h": other.encode()}, RECS, ["LL_DEV_SetSize"])
    assert [c["name"] for c in doc["functions"][0]["parameters"][0]["constants"]] == ["LL_DEV_SIZE_32B",
                                                                                     "LL_DEV_SIZE_7B"]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    return tmp_path


SETTER = """
/**
 * @brief Select the HSI divider.
 * @param Div one of:
 *        @arg @ref LL_RCC_HSI_DIV_1
 *        @arg @ref LL_RCC_HSI_DIV_4
 */
static inline void LL_RCC_HSI_SetDivider(uint32_t Div)
{
    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= Div;
}
"""


def _with_setter(header: str) -> str:
    at = header.index("/**\n * @brief Enable the HSI oscillator.")
    return header[:at] + "#define LL_RCC_HSI_DIV_1 0x00000000U\n#define LL_RCC_HSI_DIV_4 (0x2U << 7U)\n" + \
        SETTER.lstrip("\n") + "\n" + header[at:]


def test_prepare_declares_the_extract_as_a_bound_input_without_the_code(env):
    ex = example_copy(env, header=_with_setter(HEADER),
                      mutate=lambda s: s["delivery"]["scope"]["functions"].append("LL_RCC_HSI_SetDivider"))
    ws, man = WO.prepare(ex, "WO-BF-API-1")
    decl = [i for i in man["inputs"] if i["role"] == BI.ROLE]
    assert [d["path"] for d in decl] == [BI.OUT] and decl[0]["sha256"] == sha256_file(ws / BI.OUT)
    assert BI.declared(man) == BI.OUT
    doc = json.loads((ws / BI.OUT).read_text())
    assert doc["functions"] == [{"function": "LL_RCC_HSI_SetDivider", "parameters": [{"name": "Div", "constants": [
        {"name": "LL_RCC_HSI_DIV_1", "value": "0x00000000"}, {"name": "LL_RCC_HSI_DIV_4", "value": "0x00000100"}]}]}]
    assert not (ws / "software").exists()  # the code itself still enters only after SWE.1 (FR-007)


def test_prepare_without_documented_constants_is_unchanged(env):
    ws, man = WO.prepare(example_copy(env), "WO-BF-API-2")
    assert SCOPE and BI.declared(man) is None and not (ws / BI.OUT).exists()


def test_swe1_author_and_inspector_get_the_declared_extract(env, monkeypatch):
    from forge_factory.inspection import engine
    from forge_factory.lrtx import review, swe1

    ex = example_copy(env, header=_with_setter(HEADER),
                      mutate=lambda s: s["delivery"]["scope"]["functions"].append("LL_RCC_HSI_SetDivider"))
    ws, _man = WO.prepare(ex, "WO-BF-API-3")
    g = swe1.groups(swe1.inventory(ws))[0]
    p = swe1.group_packet(ws, g, "m")
    assert BI.OUT in [s["path"] for s in p["sources"]] and BI.AUTHOR_NOTE in p["instructions"]
    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / swe1.REQS).write_text("# Software requirements\n")
    monkeypatch.setattr(engine.Store, "latest_baseline", lambda self, ph: {
        "baseline_id": f"BL-{ph}-001", "baseline_hash": "h" * 64, "files": [swe1.REQS]})
    assert BI.OUT in [s["path"] for s in review.evidence(ws, "SWE.1")[1]]
    assert BI.OUT not in [s["path"] for s in review.evidence(ws, "SWE.2")[1]]  # SWE.2+ read the code itself


def test_swe1_packets_without_the_extract_are_unchanged(env):
    from forge_factory.lrtx import swe1

    ws, _man = WO.prepare(example_copy(env), "WO-BF-API-4")
    p = swe1.group_packet(ws, swe1.groups(swe1.inventory(ws))[0], "m")
    assert BI.OUT not in [s["path"] for s in p["sources"]] and "Delivered interface" not in p["instructions"]
