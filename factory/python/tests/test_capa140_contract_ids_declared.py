"""CAPA-140 (WO-F014-SWE3-WWDGHAL-20261103-L32, recurrence of CAPA-137): the SWE.2 identifier check counted every word
of the SWE.2 work products as declared, so `&flag` passed SWE.2 because the architecture prose says "NULL flag pointer"
and SWE.3's real compile was STUCK on `'flag' undeclared`. Only file-scope C declarations count now: the macros, typedef
names, tags, enum constants, function names and file-scope variables of the SWE.2 code blocks and of the work order's
headers, plus the UPPER_CASE constants and *_t types the SWE.2 text sets in inline code (SWE.3 declares those)."""
import pytest
from forge_factory.assurance import register_contract as RC
from test_capa128_hal_on_st_ll import env  # noqa: F401 (fixture)
from test_capa137_swe2_contract_compile_triage import _ws

ARCH = ("# Software architecture\n\nA NULL flag pointer returns `HAL_ERROR`; the early wake-up status flag is read with "
        "`HAL_WWDG_GetFlag(&value)`. The window value `window` and the `counter` are checked; `HAL_WWDG_EWI_ON` enables "
        "the interrupt and `hal_status_t` is the return type.\n\n## Interface\n\n```c\n"
        "typedef struct { uint32_t window; uint32_t counter; } hal_wwdg_config_t;\n"
        "#define HAL_WWDG_WINDOW_MAX 0x7FU\n"
        "typedef enum { HAL_WWDG_PRESCALER_1 = 0, HAL_WWDG_PRESCALER_8 = 3 } hal_wwdg_prescaler_t;\n"
        "hal_status_t HAL_WWDG_Init(const hal_wwdg_config_t *p_config);\n"
        "hal_status_t HAL_WWDG_GetFlag(uint32_t *p_flag);\n"
        "static inline uint32_t hal_wwdg_helper(uint32_t arg) { uint32_t local = arg; return local; }\n```\n")


def _arch_ws(env, name, args):
    ws = _ws(env, name, args, cmsis_ll=False, function="HAL_WWDG_GetFlag")
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
    return ws


@pytest.mark.parametrize("ident", ["flag", "value", "window", "p_flag", "p_config", "local", "arg"])
def test_prose_words_parameters_members_and_locals_are_not_declarations(env, ident):
    out = RC.check_args_declared(_arch_ws(env, f"BAD-{ident}", [f"&{ident}"]))
    assert len(out) == 1 and f"'{ident}' undeclared in case C1" in out[0] and "&(uint32_t){0U}" in out[0]


@pytest.mark.parametrize("args", [
    ["&(uint32_t){0U}"],
    ["&(const hal_wwdg_config_t){ .window = HAL_WWDG_WINDOW_MAX, .counter = 0x7FU }"],  # typedef + macro + designators
    ["(uint32_t)HAL_WWDG_PRESCALER_8"], ["(uint32_t)HAL_WWDG_EWI_ON"],                   # enum constant; inline constant
    ["(hal_status_t *)NULL"], ["(uint32_t)sizeof(hal_wwdg_prescaler_t)"],              # inline type; enum typedef
    ["(uint32_t)(uintptr_t)&HAL_WWDG_Init"],                                             # a declared function name
])
def test_file_scope_declarations_and_inline_constants_stay_clean(env, args):
    assert RC.check_args_declared(_arch_ws(env, "OK", args)) == []


def test_the_scanner_takes_file_scope_names_only():
    names = RC._file_scope_names('#define M 1\nextern "C" {\ntypedef struct { int member; } t_t;\nint f(int param);\n'
                                 "static int g = 2, h;\nenum e { E1, E2 = 3 };\ntypedef void (*cb_t)(int code);\n"
                                 "static inline int body(int p) { int loc = p; return loc; }\n}\n")
    assert names == {"M", "t_t", "f", "g", "h", "e", "E1", "E2", "cb_t", "body"}
