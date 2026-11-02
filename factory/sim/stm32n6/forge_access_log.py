# ruff: noqa: F821, UP032 - Renode injects `request` and `self`; IronPython 2.7 has no f-strings
# Forge-C register-access log (owner 2026-11-02 "Allow access logging"). forge-sim-mcp appends this observer to the
# peripheral model it loads (run_image), after the model's own read/write handling: it only observes an access, the
# model has already set request.Value, and it never changes a register. A prohibition ("shall not read or write any
# register before the first call / outside a function") is verified on this log, not on final register contents.
#   * Every access to the model's window (CPU or monitor) is one line of the file named by the environment variable
#     FORGE_ACCESS_LOG (forge-sim-mcp sets it per image: <image>.access.log; the model file itself stays the same):
#         <index> <R|W> <offset hex> <value hex> <phase> <pc hex or ->
#     index counts from 0 in access order; phase is the word the test last wrote with FORGE_ACCESS_PHASE(p).
#   * The RAM access-log block at ACCESS_LOG_BASE (forge_target_test.h; in the MAILBOX region after the result
#     mailbox) lets a target test check the log itself with TCHECK: +0x00 phase (written by the test), +0x04 total
#     accesses, +0x08 + 4*p accesses made in phase p (p < 16).
# Python peripheral code takes no virtual time: the instruction count and the virtual clock are unchanged by it.
# IronPython 2.7 (Renode): no f-strings, no 0x1_000 literals.
ACCESS_LOG_BASE = 0x341F0100
if request.IsInit:
    import System
    forge_acc_bus = self.GetMachine().SystemBus
    forge_acc_n = 0
    forge_acc_path = System.Environment.GetEnvironmentVariable("FORGE_ACCESS_LOG")
    forge_acc_out = open(forge_acc_path, "w") if forge_acc_path else None
elif request.IsRead or request.IsWrite:
    forge_acc_phase = forge_acc_bus.ReadDoubleWord(ACCESS_LOG_BASE)
    try:
        forge_acc_pc = "0x{:08X}".format(int(forge_acc_bus.GetCurrentCPU().PC.RawValue))
    except Exception:  # a monitor access has no CPU context
        forge_acc_pc = "-"
    if forge_acc_out is not None:
        forge_acc_out.write("{:d} {} 0x{:03X} 0x{:08X} {:d} {}\n".format(
            forge_acc_n, "R" if request.IsRead else "W", int(request.Offset), int(request.Value) & 0xFFFFFFFF,
            int(forge_acc_phase), forge_acc_pc))
        forge_acc_out.flush()
    forge_acc_n += 1
    forge_acc_bus.WriteDoubleWord(ACCESS_LOG_BASE + 4, forge_acc_n)
    if forge_acc_phase < 16:
        forge_acc_slot = ACCESS_LOG_BASE + 8 + 4 * forge_acc_phase
        forge_acc_bus.WriteDoubleWord(forge_acc_slot, forge_acc_bus.ReadDoubleWord(forge_acc_slot) + 1)
