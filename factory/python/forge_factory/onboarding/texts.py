"""Feature 016 slice H (OB-T031): the prompt texts of a package-driven work order, generated - never written by hand per
peripheral (FR-012). The keys are the ones the feature 009/015 prompt mechanism consumes (`prompt`, and for ST's
classic HAL `prompt_st_hal` with its `replace` list); every value is a template of the driver style filled with
derived facts, the owner's scope statements, or the simulation model's own behaviour description, and records where
it came from (`template:<id>`, `owner:scope`, `model:<file>`).

The generic entries of the hand-written CRC HAL overlay (feature 015) are the templates; its domain entries became
facts (the delivered API, time base, host instance, kernel-clock stub) or generic texts that defer the concrete
values to the requirements, the RM and the simulator description."""
from __future__ import annotations

import re
from pathlib import Path

from ..common import REPO_ROOT
from .facts import value

SIM_DIR = REPO_ROOT / "factory/sim/stm32n6"


class TextsUnavailable(ValueError):
    pass


def _t(text: str, src: str) -> dict:
    return {"text": text, "from": src}


def model_description(pid: str) -> str | None:
    """The behaviour description a simulation model carries in its header comment (the model is the artifact that
    states it; feature 015 models and authored models both have one)."""
    p = SIM_DIR / f"{pid}_model.py"
    if not p.is_file():
        return None
    lines = []
    for ln in p.read_text().splitlines():
        if not ln.startswith("#"):
            break
        if "noqa" in ln:
            continue
        lines.append(ln.lstrip("#").strip())
    return " ".join(lines).strip() or None


def _example_field(pkg: dict, device_macros: set[str]) -> tuple[str, str]:
    """A register field of the RM index whose CMSIS mask macro the device header defines (for examples only)."""
    prefix = value(pkg, "register_prefix")
    regs = sorted((value(pkg, "register_index") or {}).items(), key=lambda kv: kv[1]["offset"])
    for single in (True, False):  # a single-bit field of the lowest-offset register first (USART_CR1_UE)
        for reg, d in regs:
            for f in sorted(d["fields"], key=lambda k: d["fields"][k]["lsb"]):
                fd, short = d["fields"][f], reg[len(prefix) + 1:]
                if (fd["msb"] == fd["lsb"]) == single and f"{prefix}_{short}_{f}" in device_macros:
                    return short, f
    raise TextsUnavailable("TEXTS_NO_EXAMPLE_FIELD")


def st_hal(pkg: dict, scope: list[str], system_name: str, device_macros: set[str], function_order: list[str]) -> dict:
    """`prompt` + `prompt_st_hal` for ST's classic HAL (driver style HAL_STANDALONE)."""
    P, inst = value(pkg, "register_prefix"), value(pkg, "instance")
    pid = P.lower()
    base, page, ch = value(pkg, "base_address"), value(pkg, "mm_page"), value(pkg, "rm_chapter")
    doc = ch["doc"]
    fp, hdr, api = value(pkg, "function_prefix"), value(pkg, "headers"), value(pkg, "api")
    tb = value(pkg, "time_base")
    tb = None if tb in (None, "NONE") else tb
    halh = hdr["header"]
    halstem = Path(halh).stem
    files = [f["to"] for f in (value(pkg, "file_map") or {}).get("files", [])]
    exh = [Path(f).name for f in files if f.endswith("_ex.h")]
    headers = " and ".join([halh, *exh])
    llstem = f"stm32n6xx_ll_{pid}"
    block = f"ll_{pid}_regs"
    # JSON canonicalization sorts mapping keys; the owner-provided function list is the stable sequence.
    fns = [name for name in function_order if name in api["prototypes"]]
    init_fn = next((f for f in fns if f.endswith("_Init")), fns[0])
    query = next((f for f in fns if "GetState" in f), None) or next((f for f in fns if re.search(r"Read|Get|Is", f)),
                                                                    fns[-1])
    handle = (api.get("handle") or {}).get("type")
    init = api.get("init") or {}
    state_member = next((m for m in (api.get("handle") or {}).get("members", []) if m in ("State", "gState")), None)
    state_reset = api.get("state_reset")
    reg, field = _example_field(pkg, device_macros)
    mask = f"{P}_{reg}_{field}"
    one_bit = (lambda d: d["msb"] == d["lsb"])(value(pkg, "register_index")[f"{P}_{reg}"]["fields"][field])
    effect = f"set {P}_{reg}.{field}" if one_bit else f"write the configured value to {P}_{reg}.{field}"
    model = model_description(pid)
    if model is None:
        raise TextsUnavailable(f"TEXTS_MODEL_DESCRIPTION_MISSING:{pid}")
    protos = "; ".join(api["prototypes"][f] for f in fns)
    if handle:
        api_txt = (f"Interfaces (the delivered ST HAL API exactly as declared in software/hal/{headers}: {protos}; the "
                   f"handle {handle} (Instance = {inst}, Init = {init.get('type')} with {', '.join(init.get('fields', []))}"
                   f"{'; ' + state_member if state_member else ''}) - describe what the delivered declarations are, never "
                   "a different API)")
        args = (f', e.g. "&({handle}){{ .Instance = {inst}, .Init = {{ .{init.get("fields", ["Mode"])[0]} = <a constant '
                f'of {halh}>, ... }} }}" (a handle is ALWAYS such a compound literal with .Instance = {inst} and the '
                ".Init fields the case needs: the gates bind them to the delivered code); invalid cases pass the "
                "invalid value (NULL, an out-of-range constant)")
        ut = "\n".join([f"static void ut_{pid}_init(void)", "{", f"    static {handle} h;", "    ut_reset_regs();",
                        f"    h.Instance = {inst};",
                        *([f"    h.{state_member} = {state_reset};"] if state_member and state_reset else []),
                        f"    /* h.Init.<field> = <a constant of {halh}>; - one line per Init field the case needs */",
                        *([f"    /* forge_host_{pid}.<REG> = <the flags a wait polls>; - preset: host registers are "
                           "RAM */"] if tb else []),
                        f"    CHECK(\"UT-001\", {init_fn}(&h) == HAL_OK);",
                        f"    CHECK(\"UT-002\", (forge_host_{pid}.{reg} & {mask}) == {mask});",
                        f"    CHECK(\"UT-003\", {init_fn}(NULL) == HAL_ERROR);", "}"])
        cfg = (f"a handle (static, its fields assigned: Instance = {inst}"
               f"{', ' + state_member + ' = ' + state_reset if state_member and state_reset else ''}, the Init fields)")
        query_ex = f"{query}(&h)"
        null_resp = "a NULL handle -> HAL_ERROR without register access"
    else:
        ip = api.get("instance_param") or {"type": f"{P}_TypeDef", "name": f"{P}x"}
        api_txt = (f"Interfaces (the delivered ST HAL API exactly as declared in software/hal/{headers}: {protos}; "
                   f"the functions take the instance pointer {ip['type']} *{ip['name']} (the CMSIS device structure "
                   f"{inst}) and {init.get('type', 'the configuration')} ({', '.join(init.get('fields', []))}) - "
                   "describe what the delivered declarations are, never a different API)")
        args = (f', e.g. "{inst}" and "&({init.get("type")}){{ .{init.get("fields", ["Pin"])[0]} = <a constant of '
                f'{halh}>, ... }}" (the instance is ALWAYS {inst}; a configuration is a compound literal with the '
                "fields the case needs: the gates bind them to the delivered code); invalid cases pass the invalid "
                "value (NULL, an out-of-range constant)")
        ut = "\n".join([f"static void ut_{pid}_init(void)", "{", f"    static {init.get('type')} cfg;",
                        "    ut_reset_regs();",
                        f"    /* cfg.<field> = <a constant of {halh}>; - one line per field the case needs */",
                        f"    {init_fn}({inst}, &cfg);",
                        f"    CHECK(\"UT-001\", (forge_host_{pid}.{reg} & {mask}) == {mask});", "}"])
        cfg = f"the instance {inst} and a configuration (static, its fields assigned)"
        query_ex = f"{query}({inst}, ...)"
        null_resp = "an invalid parameter -> no register access"
    host_note = (f"on the host every {P} register is plain RAM (forge_host_{pid}): a written value stays and no flag "
                 "changes by itself" + (f", so a wait needs its flag preset before the call, a timeout case leaves "
                                        f"it clear, and the time base {tb} advances 1 per call" if tb else ""))
    timing = (f"; and one timing requirement: every wait ends within the caller's timeout measured with {tb} "
              "(HAL_TIMEOUT otherwise)" if tb else f"; and one timing requirement: no {fp} function waits on a {P} "
                                                   "flag")
    target = (f"write software/tests/target/test_{pid}_target.c (the scope functions on the simulated {inst} with valid "
              f"configurations; every expected register value and result follows the simulator description and "
              f"{doc}) and software/tests/target/test_{pid}_target_errors.c (the failure responses the simulator can "
              f"produce: invalid parameters return HAL_ERROR and leave the {P} registers unchanged)")
    order = ", ".join(fns)
    integ = f"the scope functions in the order a caller uses them ({order}) with a valid and an invalid configuration"
    scope_txt = "; ".join(scope)
    prompt = {
        "swe1_cover": _t(f"Cover (only what the {P} scope names, for the instance {inst}; name the registers {P}_<REG> "
                         f"as the {doc} {P}x_ registers of the instance): {scope_txt}", "owner:scope"),
        "swe1_effect_example": _t(f'{{"case":"INIT_{field}","swr":"SWR-001","register":"{P}_{reg}","field":"{field}",'
                                  f'"op":"write","value":"0x0"}}', "template:st_hal.swe1_effect_example"),
        "swe1_effect_rule": _t('Use op "write" with "value" (an integer or "0x..." string) for a field the requirement '
                               'writes a value to, op "set"/"clear" for a single bit; a function that writes a '
                               "caller-supplied value gets one entry with a representative value and the api_calls "
                               "args pass that value. Read and query functions get op no_write with register/field.",
                               "template:st_hal.swe1_effect_rule"),
        "ll_api": _t(f"the delivered functions exactly as declared in software/hal/{headers}",
                     "template:st_hal.ll_api"),
        "swe2_static_view": _t(f"a Caller, the component {halstem} (HAL, delivered, FROZEN) and the {inst} register "
                               f"block ({base}, {doc} p.{page}) and their dependency (Caller -> HAL -> registers)",
                               "template:st_hal.swe2_static_view"),
        "swe2_dynamic_view": _t(f"participants Caller, {halstem}, {inst}, showing {order} using the delivered {fp} "
                                "function names", "template:st_hal.swe2_dynamic_view"),
        "target_model": _t(f"The simulated {inst} (factory/sim/stm32n6/{pid}_model.py): {model} Expected values in "
                           "target checks follow this model.", f"model:{pid}_model.py"),
        "field_mask_example": _t(mask, "template:st_hal.field_mask_example"),
        "requirement_example": _t(f"When the {P} initialisation is requested with a valid configuration, the "
                                  f"{system_name} shall {effect}.",
                                  "template:st_hal.requirement_example"),
        "query_example": _t(query_ex, "template:st_hal.query_example"),
    }
    st = {
        "hal_requirement_example": _t(f"When the {P} initialisation is requested with a valid configuration, the "
                                      f"{system_name} shall {effect}.",
                                      "template:st_hal.hal_requirement_example"),
        "hal_reset_example": _t(f"(e.g. '- **SWR-0nn** While no {P} initialisation has been requested after reset, "
                                f"the {system_name} shall not write any {P} register.')",
                                "template:st_hal.hal_reset_example"),
        "hal_effect_example": _t(f'{{"case":"INIT_{field}","swr":"SWR-001","register":"{P}_{reg}","field":"{field}",'
                                 f'"op":"set","status":"HAL_OK"}}', "template:st_hal.hal_effect_example"),
        "hal_failure_responses": _t(f"one requirement per failure response of the scope: {null_resp}; an invalid "
                                    "configuration value -> HAL_ERROR without writing the register it configures; "
                                    "a busy handle -> HAL_BUSY where the delivered API declares it" + timing,
                                    "template:st_hal.hal_failure_responses"),
        "hal_contract_rule": _t(f"{init_fn} with a valid configuration gets op write entries for every {P} register "
                                "field it writes for that configuration (the configured or default values), status "
                                "HAL_OK; an invalid configuration or NULL argument gets op no_write without "
                                "register/field and status HAL_ERROR; query functions get op no_write. Every case id "
                                "is unique UPPER_CASE. Never add an entry the requirement text does not state.",
                                "template:st_hal.hal_contract_rule"),
        "hal_api": _t(api_txt, "template:st_hal.hal_api"),
        "hal_dynamic_view": _t(f"showing {order} with their register accesses"
                               + (", the ready path (HAL_OK) and the timeout path (HAL_TIMEOUT)" if tb else "")
                               + f", and an invalid argument returning HAL_ERROR without register access, using the "
                                 f"delivered {fp} function names", "template:st_hal.hal_dynamic_view"),
        "hal_args_example": _t(args, "template:st_hal.hal_args_example"),
        "hal_ut_example": _t(ut, "template:st_hal.ut_example"),
        "hal_ut_rule": _t(f"Each case configures {cfg} and checks the HAL return value and the register values of "
                          f"forge_host_{pid} ({host_note}); invalid-parameter cases check HAL_ERROR and unchanged "
                          "registers; behaviour that needs the hardware is verified on the target model",
                          "template:st_hal.ut_rule"),
        "hal_integration": _t(f"({integ})", "template:st_hal.integration"),
        "hal_target_tests": _t(target, "template:st_hal.target_tests"),
        "ut_example": _t(ut, "template:st_hal.ut_example"),
        "ut_rule": _t(f"Each case configures {cfg} and checks the HAL return value and the register values of "
                      f"forge_host_{pid} ({host_note}); invalid-parameter cases check HAL_ERROR and unchanged "
                      "registers; behaviour that needs the hardware is verified on the target model",
                      "template:st_hal.ut_rule"),
        "integration": _t(f"{integ} ({host_note})", "template:st_hal.integration"),
        "target_tests": _t(target, "template:st_hal.target_tests"),
        "query_example": _t(query_ex, "template:st_hal.query_example"),
    }
    vendor = f"{P}-><REG> & {P}_<REG>_<FIELD> bits of the vendor header (e.g. {P}->{reg} & {mask})"
    hal_inc = ("'#include \"stm32n6xx_hal.h\"', '#include \"forge_target_test.h\"' (a handle or configuration is a "
               "static variable with its fields assigned - no '= {0}' initialiser: the target image has no memset)")
    replace = [
        [f"and one measurable timing requirement (every wait is bounded by {fp}TIMEOUT_VALUE = 1000 polling iterations)",
         ""],
        [f"the pass criterion uses the requirement's own bound, e.g. 'at most {fp}TIMEOUT_VALUE polling iterations', "
         "never", "the pass criterion uses the requirement's own bound, never"],
        [f"Register access (extern volatile uint32_t register-block array placed at the {P} base by the linker, indexed "
         "by offset/4; no integer-to-pointer casts; host tests define the array)",
         "Register access (the delivered design: the HAL reaches the registers through "
         + ("its handle, h->Instance->REG, with Instance" if handle else "the instance pointer, with")
         + f" the CMSIS device structure {inst} of stm32n6xx.h at the base {base}; host tests map {inst} to a RAM "
           "struct, forge_host_device.h)"],
        [f"components named {halstem} (HAL) and {llstem} (LL, header-only), the {P} register block ({base}) and their "
         "dependencies (HAL -> LL -> registers)",
         f"the component {halstem} (HAL, delivered, FROZEN), the {inst} register block ({base}, {doc} p.{page}) and "
         "their dependency (HAL -> registers" + (", through the handle's Instance)" if handle else ")")],
        [f"participants Caller, {halstem}, {llstem}, {P},", f"participants Caller, {halstem}, {inst},"],
        [f"'SWC_HAL --> SWC_LL : IF-01 LL_{P}_* accessors'", f"'Caller --> SWC_HAL : IF-02 {fp} API'"],
        ["using only the interface types and constants you define in Interfaces",
         f"using only the delivered types and constants ({', '.join(x for x in (handle, init.get('type')) if x)} and the "
         f"{halh} constants)"],
        ["SWE.3 must implement the interface so that these calls compile.", "The calls must compile against the "
                                                                             "delivered headers."],
        [f"'#include \"{halstem}.h\"', '#include \"forge_target_test.h\"'", hal_inc],
        [f"with conditions on HAL return values and {block}[LL_{P}_<REG>_OFFSET / 4U] & LL_{P}_<REG>_<FIELD>_MSK bits "
         f"(always the _MSK macro, e.g. LL_{P}_{reg}_{field}_MSK; never the field name without _MSK). No printf, no "
         f"stdlib, no {block} definition.", f"with conditions on HAL return values and {vendor}. No printf, no stdlib."],
        [f"on HAL return values and {block}[LL_{P}_<REG>_OFFSET / 4U] bits. No printf, no stdlib, no {block} definition "
         "(the linker places it).", f"on HAL return values and {vendor}. No printf, no stdlib."],
        [f"the LL_{P}_ functions to test", f"the {fp} functions to test (their declarations"
                                           + (f"; the handle {handle} and the Init constants)" if handle else ")")],
        [f"For EACH LL_{P}_ function group", f"For EACH {fp} function group"],
        ["on LL return values and", "on HAL return values and"],
        ["LL functions return nothing: no status and no ready.",
         "HAL functions return HAL_StatusTypeDef (or the value their declaration returns)."],
        [f"software/ll/{llstem}.h (the LL API and its exact names)",
         f"software/hal/{headers} (the delivered HAL API and its exact names)"],
        [f"software/ll/{llstem}.h (exact LL names)", f"software/hal/{headers} (exact HAL names)"],
        [f"Read workproducts/SWE.2/software_architecture.md, software/ll/{llstem}.h and",
         f"Read workproducts/SWE.2/software_architecture.md, software/hal/{halh} and"],
        [f"'#include \"{llstem}.h\"', '#include \"forge_target_test.h\"'", hal_inc],
        ["exercising the LL sequences a caller will use", "exercising the HAL sequences a caller will use"],
        ["exercising HAL+LL together", "exercising the delivered HAL"],
        [f"(e.g. {P}->CR & {P}_CR_<FIELD>)", f"(e.g. {P}->{reg} & {mask})"],
        ["the LL and the HAL are separate components, each exactly ONE element with the <<SWC>> stereotype",
         "the delivered HAL is exactly ONE element with the <<SWC>> stereotype"],
    ]
    st["replace"] = {"text": replace, "from": "template:st_hal.replace"}
    return {"prompt": prompt, "prompt_st_hal": st}


def device_macros(ctx) -> set[str]:
    from .identity import device_header

    dh = device_header(ctx)
    return set(re.findall(r"#define\s+(\w+)\s", dh.read_text(errors="replace"))) if dh else set()


def generate(ctx, pkg: dict) -> dict:
    """The package `texts` for the work order's driver style; {} when the style has no template set yet."""
    style = value(pkg, "driver_style")
    if style != "HAL_STANDALONE":
        return {}
    scope = ctx.spec.get("scope") if isinstance(ctx.spec.get("scope"), list) else []
    # the base instructions name the system '<P> driver' (EARS check); the examples use the same name
    return st_hal(pkg, scope, f"{value(pkg, 'register_prefix')} driver", device_macros(ctx),
                  ctx.delivery["scope"]["functions"])


def plain(texts: dict) -> dict:
    """{key: str} (and `replace` as a list) - the form the profile's prompt keys take."""
    out = {}
    for group, d in texts.items():
        out[group] = {k: v["text"] for k, v in d.items()}
    return out
