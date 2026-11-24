# Standard profiles

A profile tells the neutral forge-c-hi engine how one standard names things and how much rigor each integrity level
needs. Skills and gates never change when you switch profiles: only `.hi/project.json` does.

| Profile | Standard | Levels |
|---|---|---|
| `generic.json` | Forge-C generic high-integrity baseline (requirements quality after ISO/IEC/IEEE 29148) | HI-0..HI-4 |
| `iso26262.json` | ISO 26262:2018, road vehicles | QM, ASIL A..D |
| `iec61508.json` | IEC 61508:2010, E/E/PE systems | SIL 1..4 (HI-0 not defined) |
| `aspice40.json` | Automotive SPICE 4.0, as a process reference | process HI-0..HI-4 |
| `_template.json` | start here for a new standard | |

## Adding a standard (for example DO-178C, EN 50716 or IEC 62304)

1. Copy `_template.json` to `<id>.json`, with a lowercase id such as `do178c`, `en50716` or `iec62304`. Files whose
   name starts with `_` are never loaded.
2. **`level_map`:** map the neutral levels to the standard's own levels, for example DO-178C software levels
   (`HI-1: "DAL D"` ... `HI-4: "DAL A"`), EN 50716 SIL 1..4 or IEC 62304 classes A..C. Leave out a neutral level the
   standard has no equivalent for: projects at that level are then refused with a configuration error.
3. **`vocabulary`:** the standard's name for each stage (`sw-req`, `sw-arch`, `unit-verif` ...). Reports use these.
4. **`clause_refs`:** clause or objective **identifiers only** per stage, for example `"ISO 26262-6:2018 6"` or a
   table/objective number. Never sentences or text from the standard: the schema limits each entry to 40 characters
   and rejects sentence punctuation.
5. **`rigor`** per level:
   - `required_gates`: from `validate`, `trace`, `quality`, `governance`, `scope`, `doc-sources`, `independence`, `build`,
     `static-analysis`, `unit-test`, `verification`, `coverage`;
   - `independence`: `same-session-ok`, `separate-session` or `separate-model-family`;
   - `coverage`: statement, branch and MC/DC targets in percent, or `null`;
   - `verification_methods`: the methods accepted for requirements at that level;
   - `rework_limit`: inspection rework rounds always granted; `rework_max` (optional, default 10): the cap on further
     rounds, granted only while the open findings keep falling.
6. Keep the `disclaimer` and add `notes` that say where the rigor values come from.
7. Validate: `python3 -m pytest tests/test_profiles.py` in the package, or `hi init --profile <id> --level HI-n`.

## How rigor values are justified

The shipped values are Forge-C defaults: they follow the direction of each standard (more independence, more
structural coverage and more verification at higher levels) but they are not a reading of any standard's tables,
and they do not replace your own tailoring. Record your justification in `notes`, and have it reviewed by whoever owns
the safety or assurance case. A profile never makes a project compliant with a standard.
