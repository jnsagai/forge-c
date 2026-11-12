# swe1-author - functional-level SWE.1 (template swe1-functional-v1)

Reference of the `swe1-author` skill (forge 0.4.0) for work orders whose manifest has `swe1_level: functional` (feature 020). Register-level work orders do not use it.

## Governance task

Before any requirement, prepare the module's governance package from the governance inventory (`inputs/governance-inventory.json`) and the input section index:
1. Name the actors that use the module's public API.
2. Write the use cases: each names its actor, its goal, every in-scope delivered function it exercises and the in-scope reference-manual features it relies on.
3. Record the assumptions you make and, as an open point, every in-scope function or feature the inputs do not describe - never invent behaviour.
4. The delivered code is the implementation under analysis, never a source; out-of-scope and not-delivered capabilities get no use case.

The factory checks the coverage deterministically: an in-scope function or feature in no use case and no open point stops SWE.1 before the requirements (COVERAGE_FAIL).

## Functional-level requirements

Write each requirement at the functional/API level in **EARS** syntax with exactly one `shall`; register, bit-field and address detail and the concrete negative cases belong to SWE.3.
Attributes you write: `key`, `title`, `statement`, `type`, `precondition`, `origin_group`, `links`, `use_cases`, `verification_method`, `test_level`.
- `type`: `functional`, `design_constraint`, `architectural`.
- `origin_group`: `use_case`, `out_of_context`, `hal_design_constraint`, `state_behaviour`, `awaiting_traceability`.
- `links[].kind`: `trace`, `derive`; a link names an `input_id` of the input register that is a requirement source, and a locator; a derive link states its rationale; an `awaiting_traceability` requirement has no link.
- `verification_method`: `test`, `analysis`, `inspection`, `demonstration`; a `design_constraint` is verified by inspection.
- `test_level`: `unit`, `component`, `integration`, `qualification`, `not_testable`.
Set by the factory, never by you: `status` = draft, `asil` = QM, `cal` = 0, `allocated_interface` = not applicable until SWE.2, `allocated_operation` = not applicable until SWE.2.
Level rule: no register name, field name, register address or reset value in a statement (terms of the reference-manual register index and the device header symbols; hexadecimal addresses are refused); the delivered public API names (functions, states, option constants) are allowed.
Invalid use is stated generically (parameter validity, operation permitted in the current state, error reporting); concrete cases are left to SWE.3.
