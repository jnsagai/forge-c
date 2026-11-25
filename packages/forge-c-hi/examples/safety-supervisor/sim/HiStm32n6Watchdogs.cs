// Behavioural models for the forge-c-hi Safety Supervisor demo platform (Apache-2.0, written for this package).
// Register behaviour follows RM0486 rev 4 (RCC_RSR 14.10.8, IWDG chapter 59, WWDG chapter 60). Not a silicon model:
// no clock tree, no oscillator tolerance, no security or privilege filtering, no early-wakeup interrupts.
using System;
using System.Collections.Generic;
using Antmicro.Renode.Core;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Peripherals.UART;
using Antmicro.Renode.Time;

namespace Antmicro.Renode.Peripherals.Timers
{
    // Reset flags only; every other RCC register is plain storage. The flags survive a reset and are cleared by RMVF.
    public class HiRcc : IDoubleWordPeripheral, IKnownSize
    {
        public HiRcc(IMachine machine) { this.machine = machine; }
        public long Size => 0x2000;
        public void NoteReset(uint flag) { cause = flag; }
        public event Action<uint> Resetting;
        public void Reset()
        {
            if(!started) { started = true; return; }
            flags |= cause == 0 ? SoftwareReset : cause;   // a reset no watchdog asked for is a software reset
            Resetting?.Invoke(cause == 0 ? SoftwareReset : cause);
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

    // Free-running 32-bit up-counter with four compare channels (output-compare flags only: no capture, no outputs, no DMA,
    // auto-reload fixed at 0xFFFFFFFF). Written because a write to DIER makes Renode's STM32_Timer lose the pending match
    // of the other channels (selftest/test_rearm.c). Flags are set whatever DIER says; a compare value equal to the
    // present count matches only after the counter has wrapped (the product must not rely on either outcome).
    public class HiTimer : IDoubleWordPeripheral, IKnownSize
    {
        public HiTimer(IMachine machine, long frequency)
        {
            this.machine = machine;
            IRQ = new GPIO();
            raw = new LimitTimer(machine.ClockSource, (ulong)frequency, this, "count", 1ul << 62, Direction.Ascending, false,
                                 WorkMode.Periodic, true, true);
            match = new LimitTimer[Channels];
            for(var i = 0; i < Channels; i++)
            {
                var n = i;
                match[i] = new LimitTimer(machine.ClockSource, (ulong)frequency, this, "compare" + (i + 1), 1ul << 62,
                                          Direction.Descending, false, WorkMode.OneShot, true, true);
                match[i].LimitReached += () => Matched(n);
            }
            Reset();
        }
        public long Size => 0x400;
        public GPIO IRQ { get; }
        public void Reset()
        {
            cr1 = 0; dier = 0; sr = 0; psc = 0; pscActive = 0; start = 0;
            Array.Clear(ccr, 0, Channels);
            Array.Clear(other, 0, other.Length);
            raw.Reset(); raw.Enabled = false;
            foreach(var m in match) { m.Reset(); m.Enabled = false; }
            IRQ.Set(false);
        }
        public uint ReadDoubleWord(long offset)
        {
            switch(offset)
            {
            case 0x00: return cr1;
            case 0x0C: return dier;
            case 0x10: return sr;
            case 0x24: Sync(); return Count();
            case 0x28: return psc;
            case 0x2C: return 0xFFFFFFFF;
            case 0x34: case 0x38: case 0x3C: case 0x40: return ccr[(offset - 0x34) / 4];
            default: return other[offset / 4];
            }
        }
        public void WriteDoubleWord(long offset, uint value)
        {
            Sync();
            switch(offset)
            {
            case 0x00: cr1 = value; raw.Enabled = (value & 1) != 0; ScheduleAll(); break;
            case 0x0C: dier = value; UpdateInterrupt(); break;
            case 0x10: sr &= value; UpdateInterrupt(); break;                  // rc_w0
            case 0x14:
                if((value & 1) != 0) { pscActive = psc; SetCount(0); sr |= 1; UpdateInterrupt(); }
                break;
            case 0x24: SetCount(value); break;
            case 0x28: psc = value & 0xFFFF; break;                            // taken over by the next update event
            case 0x2C: if(value != 0xFFFFFFFF) { this.Log(LogLevel.Error, "auto-reload 0x{0:X} is not modelled", value); } break;
            case 0x34: case 0x38: case 0x3C: case 0x40:
                var n = (int)((offset - 0x34) / 4);
                ccr[n] = value;
                Schedule(n);
                break;
            default: other[offset / 4] = value; break;
            }
        }
        private ulong Divider => (ulong)pscActive + 1;
        private ulong Ticks => raw.Value;
        private uint Count() { return (uint)(start + Ticks / Divider); }
        private void SetCount(uint value) { raw.Value = 0; start = value; ScheduleAll(); }
        private void ScheduleAll() { for(var i = 0; i < Channels; i++) { Schedule(i); } }
        private void Schedule(int n)
        {
            var delta = (ulong)(uint)(ccr[n] - Count());
            if(delta == 0) { delta = 1ul << 32; }
            Load(n, (Ticks / Divider + delta) * Divider - Ticks);
        }
        private void Load(int n, ulong ticks)
        {
            match[n].Enabled = false;
            match[n].Limit = ticks; match[n].Value = ticks;
            match[n].Enabled = raw.Enabled;
        }
        private void Matched(int n)
        {
            sr |= 2u << n;
            Load(n, (1ul << 32) * Divider);
            UpdateInterrupt();
        }
        private void UpdateInterrupt() { IRQ.Set((sr & dier & 0x1F) != 0); }
        private void Sync() { if(machine.SystemBus.TryGetCurrentCPU(out var cpu)) { cpu.SyncTime(); } }
        private const int Channels = 4;
        private uint cr1, dier, sr, psc, pscActive, start;
        private readonly uint[] ccr = new uint[Channels], other = new uint[0x100];
        private readonly IMachine machine; private readonly LimitTimer raw; private readonly LimitTimer[] match;
    }

    // Verification equipment, not a device: what an observer of the external interfaces would record, readable by a test
    // program. Nothing it holds is changed by a reset of the machine. Times are virtual microseconds since power-on.
    //   +00 time now
    //   +08 characters USART1 has sent   +0C select one   +10 the character   +14 time of its transmit register write
    //   +20 output level changes of GPIOA 0..15   +24 select one   +28 pin | level << 8   +2C its time
    //   +30 resets   +34 select one   +38 its cause as an RCC_RSR flag   +3C its time
    //   +40 write: USART1 receives this character now
    public class HiMonitor : IDoubleWordPeripheral, IGPIOReceiver, IKnownSize
    {
        public HiMonitor(IMachine machine, HiRcc rcc, IUART uart)
        {
            this.machine = machine; this.uart = uart;
            uart.CharReceived += c => sent.Add(Tuple.Create((uint)c, Now()));
            rcc.Resetting += cause => resets.Add(Tuple.Create(cause, Now()));
        }
        public long Size => 0x400;
        public void OnGPIO(int number, bool value) { pins.Add(Tuple.Create((uint)number | (value ? 0x100u : 0u), Now())); }
        public void Reset() { }                                 // the observer is not reset with the machine
        public uint ReadDoubleWord(long offset)
        {
            if(machine.SystemBus.TryGetCurrentCPU(out var cpu)) { cpu.SyncTime(); }
            switch(offset)
            {
            case 0x00: return Now();
            case 0x08: return (uint)sent.Count;
            case 0x10: return At(sent, select[0]).Item1;
            case 0x14: return At(sent, select[0]).Item2;
            case 0x20: return (uint)pins.Count;
            case 0x28: return At(pins, select[1]).Item1;
            case 0x2C: return At(pins, select[1]).Item2;
            case 0x30: return (uint)resets.Count;
            case 0x38: return At(resets, select[2]).Item1;
            case 0x3C: return At(resets, select[2]).Item2;
            default: return 0;
            }
        }
        public void WriteDoubleWord(long offset, uint value)
        {
            switch(offset)
            {
            case 0x0C: select[0] = value; break;
            case 0x24: select[1] = value; break;
            case 0x34: select[2] = value; break;
            case 0x40: uart.WriteChar((byte)value); break;
            default: this.Log(LogLevel.Error, "the monitor has no register 0x{0:X}", offset); break;
            }
        }
        private static Tuple<uint, uint> At(List<Tuple<uint, uint>> list, uint n)
        {
            return n < list.Count ? list[(int)n] : Tuple.Create(0xFFFFFFFFu, 0xFFFFFFFFu);
        }
        private uint Now() { return (uint)(machine.ElapsedVirtualTime.TimeElapsed.TotalMicroseconds); }
        private readonly List<Tuple<uint, uint>> sent = new List<Tuple<uint, uint>>(), pins = new List<Tuple<uint, uint>>(),
                                                 resets = new List<Tuple<uint, uint>>();
        private readonly uint[] select = new uint[3];
        private readonly IMachine machine; private readonly IUART uart;
    }
}
