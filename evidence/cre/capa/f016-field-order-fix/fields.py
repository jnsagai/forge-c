from forge_factory.assurance.hardware import parse_section
for suffix, first in (("L", 0), ("H", 8)):
    text = f"#### GPIO configuration (GPIOx_ADVCFGR{suffix})\nAddress offset: 0x48\nReset value: 0x0000 0000\nBits 31, 27, 23, 19, RETy: test (y = {first+7} to {first})\n    15, 11, 7, 3  0: disabled\n"
    reg = parse_section(text, "GPIO")
    if f"RET{first}" not in reg["fields"]:
        print("SYMPTOM_PRESENT:RM parser omits comma-separated GPIO pin fields")
        raise SystemExit(1)
    assert reg["fields"][f"RET{first}"]["lsb"] == 3
    assert reg["fields"][f"RET{first+7}"]["lsb"] == 31
print("SYMPTOM_ABSENT")
