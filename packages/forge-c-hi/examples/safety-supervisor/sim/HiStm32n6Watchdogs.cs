// Behavioural models for the forge-c-hi Safety Supervisor demo platform (Apache-2.0, written for this package).
// Register behaviour follows RM0486 rev 4 (RCC_RSR 14.10.8, IWDG chapter 59, WWDG chapter 60). Not a silicon model:
// no clock tree, no oscillator tolerance, no security or privilege filtering, no early-wakeup interrupts.
using System;
using Antmicro.Renode.Core;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Time;

namespace Antmicro.Renode.Peripherals.Timers
{
    // Reset flags only; every other RCC register is plain storage. The flags survive a reset and are cleared by RMVF.
    public class HiRcc : IDoubleWordPeripheral, IKnownSize
    {
        public HiRcc(IMachine machine) { this.machine = machine; }
        public long Size => 0x2000;
        public void NoteReset(uint flag) { cause = flag; }
        public void Reset()
        {
            if(!started) { started = true; return; }
            flags |= cause == 0 ? SoftwareReset : cause;   // a reset no watchdog asked for is a software reset
            cause = 0;
            Array.Clear(regs, 0, regs.Length);
        }
        public uint ReadDoubleWord(long offset) { return offset == 0x34 ? flags : regs[offset / 4]; }
        public void WriteDoubleWord(long offset, uint value)
        {
            if(offset == 0x34) { if((value & (1u << 16)) != 0) { flags = 0; } return; }
            regs[offset / 4] = value;
        }
        public const uint WindowWatchdogReset = 1u << 28, IndependentWatchdogReset = 1u << 26, SoftwareReset = 1u << 24;
        private uint flags = 0x00A00000, cause;
        private bool started = true;
        private readonly uint[] regs = new uint[0x800];
        private readonly IMachine machine;
    }

    public class HiWwdg : IDoubleWordPeripheral, IWordPeripheral, IKnownSize
    {
        public HiWwdg(IMachine machine, HiRcc rcc, long frequency)
        {
            this.machine = machine; this.rcc = rcc; this.pclk = frequency;
            timer = new LimitTimer(machine.ClockSource, (ulong)Math.Max(1, frequency / 4096), this, "wwdg", 128,
                                   Direction.Descending, true, WorkMode.Periodic, true, true);
            timer.LimitReached += Tick;
            Reset();
        }
        public long Size => 0x400;
        public void Reset()
        {
            counter = 0x7F; window = 0x7F; tb = 0; active = false; ewif = false; fired = false;
            timer.Reset(); timer.Enabled = true; SetBase();
        }
        public uint ReadDoubleWord(long offset)
        {
            switch(offset)
            {
            case 0x0: return (active ? 0x80u : 0u) | counter;
            case 0x4: return (tb << 11) | window;
            case 0x8: return ewif ? 1u : 0u;
            default: return 0;
            }
        }
        public void WriteDoubleWord(long offset, uint value)
        {
            switch(offset)
            {
            case 0x0:
                var early = active && counter > window;
                active |= (value & 0x80) != 0;
                counter = value & 0x7F;
                if(active && (early || (counter & 0x40) == 0)) { Fire(early ? "early refresh" : "T6 cleared"); }
                break;
            case 0x4: tb = (value >> 11) & 7; window = value & 0x7F; SetBase(); break;
            case 0x8: if((value & 1) == 0) { ewif = false; } break;
            }
        }
        public ushort ReadWord(long offset) { return (ushort)ReadDoubleWord(offset); }
        public void WriteWord(long offset, ushort value) { WriteDoubleWord(offset, value); }
        private void SetBase() { timer.Reset(); timer.Enabled = true; timer.Frequency = (ulong)Math.Max(1, pclk / 4096); timer.Limit = 1ul << (int)tb; timer.Value = timer.Limit; }
        private void Tick()
        {
            counter = (counter - 1) & 0x7F;
            if(counter == 0x40) { ewif = true; }
            if(active && counter == 0x3F) { Fire("not refreshed in time"); }
        }
        private void Fire(string why)
        {
            if(fired) { return; }
            fired = true;
            this.Log(LogLevel.Info, "window watchdog reset: {0}", why);
            rcc.NoteReset(HiRcc.WindowWatchdogReset);
            machine.RequestReset();
        }
        private uint counter, window, tb;
        private bool active, ewif, fired;
        private readonly long pclk;
        private readonly IMachine machine; private readonly HiRcc rcc; private readonly LimitTimer timer;
    }

    public class HiIwdg : IDoubleWordPeripheral, IKnownSize
    {
        public HiIwdg(IMachine machine, HiRcc rcc, long frequency = 32000)
        {
            this.machine = machine; this.rcc = rcc; this.lsi = frequency;
            timer = new LimitTimer(machine.ClockSource, (ulong)frequency, this, "iwdg", 0x1000, Direction.Descending, false,
                                   WorkMode.OneShot, true, true);
            timer.LimitReached += () => Fire("not refreshed in time");
            Reset();
        }
        public long Size => 0x400;
        public void Reset() { pr = 0; rlr = 0xFFF; winr = 0xFFF; on = false; unlocked = false; fired = false; timer.Reset(); timer.Enabled = false; }
        public uint ReadDoubleWord(long offset)
        {
            switch(offset)
            {
            case 0x4: return pr;
            case 0x8: return rlr;
            case 0xC: return on ? 0x100u : 0u;     // register updates are immediate: no update flag is ever pending
            case 0x10: return winr;
            default: return 0;
            }
        }
        public void WriteDoubleWord(long offset, uint value)
        {
            switch(offset)
            {
            case 0x0:
                var key = value & 0xFFFF;
                unlocked = key == 0x5555;
                if(key == 0xCCCC && !on) { on = true; Load(0xFFF); }
                if(key == 0xAAAA && on)
                {
                    if(winr < 0xFFF && timer.Value > winr + 1) { Fire("early refresh"); } else { Load(rlr); }
                }
                break;
            case 0x4: if(unlocked) { pr = value & 0xF; if(on) { Load(timer.Value - 1); } } break;
            case 0x8: if(unlocked) { rlr = value & 0xFFF; } break;
            case 0x10: if(unlocked) { winr = value & 0xFFF; if(on) { Load(rlr); } } break;
            }
        }
        private void Load(ulong ticks)
        {
            timer.Reset(); timer.Enabled = false;
            timer.Frequency = (ulong)Math.Max(1, lsi / (4L << (int)Math.Min(pr, 8u)));
            timer.Limit = ticks + 1; timer.Value = timer.Limit; timer.Enabled = true;
        }
        private void Fire(string why)
        {
            if(fired) { return; }
            fired = true;
            this.Log(LogLevel.Info, "independent watchdog reset: {0}", why);
            rcc.NoteReset(HiRcc.IndependentWatchdogReset);
            machine.RequestReset();
        }
        private uint pr, rlr, winr;
        private bool on, unlocked, fired;
        private readonly long lsi;
        private readonly IMachine machine; private readonly HiRcc rcc; private readonly LimitTimer timer;
    }
}
