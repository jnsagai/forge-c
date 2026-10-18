"""CAPA-038 (r126/r127/r123) — generated test double of the PROVIDED LL API for HAL unit tests (isolation).

HAL unit tests ran on a plain RAM array: a status flag never became set after N polls and the driver's write order was
invisible, so the SWE.4 authors invented write-capture helpers that observed only their own writes and the
inspector's demands (number of RCC_SR polls, set-then-clear order) could not be met; SWE.4 failed 3 of 4 HAL runs.

The fake is derived from the provided, read-only LL header text: every #define, type, comment and guard is kept;
each `static inline` LL function body is replaced by a call that records the call (and scalar arguments) in one
shared log; every `uint32_t` query returns a scripted value (default 0U = never set). The register array is not
declared, so a HAL that bypasses the LL fails to compile in its unit test. The shared state is defined once, in the
test translation unit that defines LL_FAKE_IMPLEMENTATION before including the HAL header.
It is test infrastructure only (no test logic); the real LL is used in SWE.5 integration and by the EASA oracle.
run_unit regenerates it and fails when the file differs (an agent must not edit it).
CAPA-043 (r146/r144): a test preset 'already enabled' state by calling the internal bit helper with a magic index; the
fake now offers ll_fake_set_state(query_fn, value), the helpers are named ll_fake_internal_* and run_unit fails a test
that calls them.
"""
from __future__ import annotations

import re
from pathlib import Path

FAKE_DIR = "software/tests/unit/ll_fake"
FAKE_HEADER = f"{FAKE_DIR}/stm32n6xx_ll_rcc.h"
# CAPA-043 (r146): tests preset state through internal helpers with magic bit indices; they are internal now
INTERNAL_CALL = re.compile(r"\bll_fake_(?:internal_\w+|record|query|set_bit|query_bit)\s*\(")
LOG_CAPACITY = 4096
_FN = re.compile(r"static\s+inline\s+(void|uint32_t)\s+(LL_\w+)\s*\(([^)]*)\)\s*\{")
_REG = r"ll_rcc_regs\[\s*(\w+)\s*/\s*4U?\s*\]"
_SET = re.compile(_REG + r"\s*\|=\s*(\w+)\s*;")
_CLR = re.compile(_REG + r"\s*&=\s*~\s*\(?\s*(\w+)\s*\)?\s*;")
_GET = re.compile(r"\(\s*" + _REG + r"\s*&\s*(\w+)\s*\)")
_REGS = re.compile(r"^[ \t]*extern\s+volatile\s+uint32_t\s+\w+\s*\[[^\]]*\]\s*;[ \t]*\n?", re.M)


def _body_end(text: str, open_brace: int) -> int:
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError("unbalanced braces in the provided LL header")


def _params(text: str) -> list[str]:
    text = text.strip()
    if text in ("", "void"):
        return []
    names = []
    for p in text.split(","):
        toks = p.replace("*", " ").split()
        names.append(toks[-1])
    return names


API = """
/* ---- test double API (generated) -------------------------------------------------------------------------- */
typedef enum
{{
{enum}
    LL_FAKE_COUNT
}} ll_fake_fn_t;

/** Clear the call log, counters, scripts and bit state. A query that reads a bit an LL function writes (e.g.
 *  IsEnabled after Enable/Disable, reset state after ForceReset/ReleaseReset) then follows that bit, as the LL
 *  does; a flag that only hardware sets (e.g. IsReady) returns 0U until scripted. */
void ll_fake_reset(void);
/** From the nth call on (1 = first call) the query fn returns value (e.g. ready after 3 polls: (fn, 3U, 1U));
 *  a script overrides the bit state of a state query. */
void ll_fake_return_from(ll_fake_fn_t fn, uint32_t nth_call, uint32_t value);
/** Number of calls of fn since the last reset. */
uint32_t ll_fake_calls(ll_fake_fn_t fn);
/** Number of recorded calls (all functions, in order; at most {cap}). */
uint32_t ll_fake_log_count(void);
/** The i-th recorded call (0 = first); LL_FAKE_COUNT when i is out of range. */
ll_fake_fn_t ll_fake_log_at(uint32_t i);
/** Log position of the k-th call of fn (k = 1 first), or -1: for order checks such as enable before disable. */
int32_t ll_fake_index_of(ll_fake_fn_t fn, uint32_t k);
/** Argument j (0 = first) of the last call of fn; 0U if fn takes no argument or was not called. */
uint32_t ll_fake_last_arg(ll_fake_fn_t fn, uint32_t j);
/** Preset the state that the state query fn reads (e.g. (LL_FAKE_LL_RCC_ADC12_IsEnabled, 1U): already enabled),
 *  without recording an LL call; returns 1U, or 0U and changes nothing when fn is not a state query (IsReady-type
 *  flags are scripted with ll_fake_return_from). */
uint32_t ll_fake_set_state(ll_fake_fn_t fn, uint32_t value);

/* internal - called only by the generated LL bodies above; run_unit fails a test that calls them (CAPA-043) */
void ll_fake_internal_record(ll_fake_fn_t fn, uint32_t a0, uint32_t a1);
uint32_t ll_fake_internal_query(ll_fake_fn_t fn, uint32_t a0, uint32_t a1);
void ll_fake_internal_set_bit(uint32_t k, uint32_t v);
uint32_t ll_fake_internal_query_bit(ll_fake_fn_t fn, uint32_t k);

#ifdef LL_FAKE_IMPLEMENTATION
static ll_fake_fn_t ll_fake_log_[{cap}U];
static uint32_t ll_fake_n_;
static uint32_t ll_fake_calls_[LL_FAKE_COUNT];
static uint32_t ll_fake_from_[LL_FAKE_COUNT];
static uint32_t ll_fake_value_[LL_FAKE_COUNT];
static uint32_t ll_fake_args_[LL_FAKE_COUNT][2];
static uint32_t ll_fake_bits_[{nbits}U];
static const uint32_t ll_fake_state_bit_[LL_FAKE_COUNT + 1] = {{ {state_bits}0U }}; /* bit index + 1; 0 = none */

void ll_fake_reset(void)
{{
    uint32_t i;
    ll_fake_n_ = 0U;
    for (i = 0U; i < (uint32_t)LL_FAKE_COUNT; i++)
    {{
        ll_fake_calls_[i] = 0U;
        ll_fake_from_[i] = 0U;
        ll_fake_value_[i] = 0U;
        ll_fake_args_[i][0] = 0U;
        ll_fake_args_[i][1] = 0U;
    }}
    for (i = 0U; i < {nbits}U; i++)
    {{
        ll_fake_bits_[i] = 0U;
    }}
}}

void ll_fake_return_from(ll_fake_fn_t fn, uint32_t nth_call, uint32_t value)
{{
    ll_fake_from_[fn] = nth_call;
    ll_fake_value_[fn] = value;
}}

uint32_t ll_fake_calls(ll_fake_fn_t fn) {{ return ll_fake_calls_[fn]; }}
uint32_t ll_fake_log_count(void) {{ return ll_fake_n_; }}
ll_fake_fn_t ll_fake_log_at(uint32_t i) {{ return (i < ll_fake_n_ && i < {cap}U) ? ll_fake_log_[i] : LL_FAKE_COUNT; }}

int32_t ll_fake_index_of(ll_fake_fn_t fn, uint32_t k)
{{
    uint32_t i;
    uint32_t seen = 0U;
    for (i = 0U; (i < ll_fake_n_) && (i < {cap}U); i++)
    {{
        if (ll_fake_log_[i] == fn)
        {{
            seen++;
            if (seen == k)
            {{
                return (int32_t)i;
            }}
        }}
    }}
    return -1;
}}

uint32_t ll_fake_last_arg(ll_fake_fn_t fn, uint32_t j) {{ return (j < 2U) ? ll_fake_args_[fn][j] : 0U; }}

uint32_t ll_fake_set_state(ll_fake_fn_t fn, uint32_t value)
{{
    if ((fn >= LL_FAKE_COUNT) || (ll_fake_state_bit_[fn] == 0U))
    {{
        return 0U;
    }}
    ll_fake_bits_[ll_fake_state_bit_[fn] - 1U] = (value != 0U) ? 1U : 0U;
    return 1U;
}}

void ll_fake_internal_record(ll_fake_fn_t fn, uint32_t a0, uint32_t a1)
{{
    if (ll_fake_n_ < {cap}U)
    {{
        ll_fake_log_[ll_fake_n_] = fn;
    }}
    ll_fake_n_++;
    ll_fake_calls_[fn]++;
    ll_fake_args_[fn][0] = a0;
    ll_fake_args_[fn][1] = a1;
}}

uint32_t ll_fake_internal_query(ll_fake_fn_t fn, uint32_t a0, uint32_t a1)
{{
    ll_fake_internal_record(fn, a0, a1);
    return ((ll_fake_from_[fn] != 0U) && (ll_fake_calls_[fn] >= ll_fake_from_[fn])) ? ll_fake_value_[fn] : 0U;
}}

void ll_fake_internal_set_bit(uint32_t k, uint32_t v) {{ ll_fake_bits_[k] = v; }}

uint32_t ll_fake_internal_query_bit(ll_fake_fn_t fn, uint32_t k)
{{
    ll_fake_internal_record(fn, 0U, 0U);
    return ((ll_fake_from_[fn] != 0U) && (ll_fake_calls_[fn] >= ll_fake_from_[fn])) ? ll_fake_value_[fn] : ll_fake_bits_[k];
}}
#endif /* LL_FAKE_IMPLEMENTATION */
"""


def generate(ll_header: str) -> str:
    fns = [(m.group(1), m.group(2), _params(m.group(3)), m.start(), m.end() - 1) for m in _FN.finditer(ll_header)]
    if not fns:
        raise ValueError("no static inline LL function in the provided header")
    bodies = {name: ll_header[brace:_body_end(ll_header, brace)] for _, name, _, _, brace in fns}
    written = {}  # (register offset macro, mask macro) -> state bit index: bits some LL function writes
    for b in bodies.values():
        for m in list(_SET.finditer(b)) + list(_CLR.finditer(b)):
            written.setdefault((m.group(1), m.group(2)), len(written))
    out, pos, state = [], 0, {}
    for ret, name, params, _start, brace in fns:
        end = _body_end(ll_header, brace)
        b = bodies[name]
        args = ", ".join([f"(uint32_t)({p})" for p in params[:2]] + ["0U"] * (2 - min(2, len(params))))
        get = _GET.search(b)
        if ret == "uint32_t" and get and (get.group(1), get.group(2)) in written:  # state query (IsEnabled ...)
            state[name] = written[(get.group(1), get.group(2))]
            call = f"return ll_fake_internal_query_bit(LL_FAKE_{name}, {state[name]}U);"
        elif ret == "uint32_t":  # a flag only hardware sets (IsReady ...): scripted, default 0U
            call = f"return ll_fake_internal_query(LL_FAKE_{name}, {args});"
        else:
            sets = [f"ll_fake_internal_set_bit({written[(m.group(1), m.group(2))]}U, 1U); " for m in _SET.finditer(b)]
            clrs = [f"ll_fake_internal_set_bit({written[(m.group(1), m.group(2))]}U, 0U); " for m in _CLR.finditer(b)]
            call = "".join(sets + clrs) + f"ll_fake_internal_record(LL_FAKE_{name}, {args});"
        out.append(ll_header[pos:brace] + "{\n    " + "".join(f"(void)({p}); " for p in params[2:]) + call + "\n}")
        pos = end
    body = "".join(out) + ll_header[pos:]
    body = _REGS.sub("/* register array not declared: HAL unit tests observe the LL API only (CAPA-038) */\n", body)
    api = API.format(enum="\n".join(f"    LL_FAKE_{n}," for _, n, _, _, _ in fns), cap=LOG_CAPACITY,
                     nbits=max(1, len(written)), state_bits="".join(f"{state[n] + 1 if n in state else 0}U, "
                                                                     for _, n, _, _, _ in fns))
    banner = ("/* GENERATED by forge_factory.workflow.ll_fake from the provided LL header - HAL unit-test double, do "
              "not edit (run_unit regenerates and compares it). */\n")
    # the API (enum + prototypes) goes before the first LL function (and its doc comment): the text before it is
    # unchanged, so its offset is the same in the generated body
    at = fns[0][3]
    c = body.rfind("/*", 0, at)
    if c >= 0 and body.find("*/", c) != -1 and not body[body.find("*/", c) + 2:at].strip():
        at = c
    return banner + body[:at] + api.lstrip("\n") + "\n" + body[at:]

def internal_calls(test_source: str) -> list[str]:
    """Names of fake-internal helpers a unit test calls (comments ignored)."""
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", test_source, flags=re.S)
    return sorted({m.group(0).rstrip("( \t") for m in INTERNAL_CALL.finditer(code)})


def write(ws: Path) -> bool:
    """Generate the fake for a HAL work order with the isolation profile; False when not applicable."""
    from ..layer import LL_HEADER

    src = Path(ws) / LL_HEADER
    if not src.is_file():
        return False
    p = Path(ws) / FAKE_HEADER
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.chmod(0o644)
    p.write_text(generate(src.read_text(errors="replace")))
    p.chmod(0o444)
    return True


def modified(ws: Path) -> bool:
    """True when the fake differs from what the provided LL header generates (it was edited)."""
    from ..layer import LL_HEADER

    p, src = Path(ws) / FAKE_HEADER, Path(ws) / LL_HEADER
    return p.is_file() and src.is_file() and p.read_text(errors="replace") != generate(src.read_text(errors="replace"))
