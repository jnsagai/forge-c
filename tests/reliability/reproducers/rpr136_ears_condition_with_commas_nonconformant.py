"""RPR-136 (local run WO-F014-SWE1-WWDGHAL-20261103-L32, Omniverse2, 2026-11-03): the WWDG HAL SWE.1 was BLOCKED
after three rework cycles (~70 author tool calls). Its negative-path requirements list several invalid arguments in
one EARS condition ("If ... a NULL pointer, a prescaler above 7, ..., or ..., then the WWDG driver shall ...") and an
event over several operations ("When the WWDG driver performs activation, configuration or refresh, the WWDG driver
shall not wait ..."). EARS allows commas in the condition, but inspection/ears.py split the condition at its FIRST
comma (`[^,]+`), so both were EARS_PATTERN_NONCONFORMANT, with no hint of why.

Scenario (synthetic statements, deterministic checker only): an UNWANTED and an EVENT requirement whose condition
contains commas, each followed by ", [then] the <system> shall". Symptom: either is not classified (UNWANTED / EVENT)
or the system name is not taken from the phrase before 'shall'. Controls (a loosened check is an error, not ABSENT):
a statement with one 'shall' but no '<system> shall' after the condition stays NONCONFORMANT, a weak modal is still
reported, and a comma-free EVENT requirement keeps its pattern."""
import sys

SIG = "an EARS condition containing commas is NONCONFORMANT although it ends with ', [then] the <system> shall'"
SYSTEM = "RCC driver"
UNWANTED = ("If the RCC driver is called with a NULL handle, a divider above 15, or a clock source other than HSI or "
            "HSE, then the RCC driver shall return RCC_ERROR without writing any RCC register.")
EVENT = "When the RCC driver performs enable, reset or release, the RCC driver shall not wait on a ready flag."
NO_SYSTEM = "If the handle is NULL, a divider above 15 shall be rejected by the RCC driver."
WEAK = "When the RCC driver performs enable, reset or release, the RCC driver shall return and may log the event."
PLAIN = "When the RCC driver is enabled, the RCC driver shall set the ON bit."


def main() -> int:
    from forge_factory.inspection.ears import check_document

    rows = {"SWR-001": UNWANTED, "SWR-002": EVENT, "SWR-003": NO_SYSTEM, "SWR-004": WEAK, "SWR-005": PLAIN}
    md = "".join(f"- **{k}** {v}\n" for k, v in rows.items())
    rep = check_document(md, {SYSTEM})
    per = {r["id"]: r for r in rep["per_requirement"]}
    if set(per) != set(rows):
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:extracted {sorted(per)}")
        return 2
    # controls
    if per["SWR-003"]["pattern"] is not None or not any("NONCONFORMANT" in f for f in per["SWR-003"]["findings"]):
        print(f"REPRODUCER_ERROR:CONTROL_LOOSENED:no-system statement classified {per['SWR-003']['pattern']}")
        return 2
    if not any("WEAK_MODAL" in f for f in per["SWR-004"]["findings"]):
        print("REPRODUCER_ERROR:CONTROL_LOOSENED:weak modal 'may' not reported")
        return 2
    if per["SWR-005"]["pattern"] != "EVENT" or per["SWR-005"]["findings"]:
        print(f"REPRODUCER_ERROR:CONTROL_CHANGED:comma-free EVENT {per['SWR-005']['pattern']} {per['SWR-005']['findings']}")
        return 2
    bad = [f"{k} {per[k]['pattern']} {per[k]['findings'][:2]}" for k, want in (("SWR-001", "UNWANTED"),
                                                                                ("SWR-002", "EVENT"))
           if per[k]["pattern"] != want or per[k]["findings"]]
    if bad:
        print("observed: " + "; ".join(bad))
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
