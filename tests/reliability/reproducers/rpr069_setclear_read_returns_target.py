"""RPR-069 (rc1 0008a): the RCC Renode model returned the TARGET register on a read of a set/clear register (RCC_CSR
read = RCC_CR), so a full-register snapshot changed at RCC_CSR when RCC_CR was written; RM0486 marks the set/clear
fields write-only ('w'). The SWE.6 author escalated DEF-003 (FACTORY) and the package stayed BLOCKED."""
import sys

SIG = "a read of a write-only set/clear register returns its target register"


class Req:
    def __init__(self, kind, off, val=0):
        self.IsInit, self.IsRead, self.IsWrite = kind == "init", kind == "read", kind == "write"
        self.Offset, self.Value = off, val


def main() -> int:
    from forge_factory.common import REPO_ROOT

    code = compile((REPO_ROOT / "factory/sim/stm32n6/rcc_model.py").read_text(), "rcc_model.py", "exec")
    env: dict = {}

    def call(kind, off, val=0):
        r = Req(kind, off, val)
        env["request"] = r
        exec(code, env)  # noqa: S102 - the factory's own model script, as Renode runs it
        return r.Value

    call("init", 0)
    call("write", 0x000, 0x8)            # RCC_CR.HSION written directly
    csr = call("read", 0x800)           # RCC_CSR (write-only set register)
    call("write", 0x800, 0x10)          # set HSEON through RCC_CSR
    cr = call("read", 0x000)
    if csr != 0 or cr != 0x18:
        print(f"RCC_CSR read 0x{csr:X}, RCC_CR 0x{cr:X}")
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
