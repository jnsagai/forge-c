# Feature 005 (AFO) status - generated from evidence records

Generated 2026-10-19T09:40:01.067827Z. status from executed evidence and the blocker register only; tasks.md boxes stay unchecked.

Tasks: BLOCKED 2, NOT_RUN 22, PARTIAL 2, PASS 49.
FRs: COVERED 45, OPEN 15, PARTIAL 12.

| Task | M | P | Status | ATs | Evidence / reason |
|---|---|---|---|---|---|
| AFO-T001 | M0 | P0 | PASS | AT-065, AT-066 | evidence/v0.4/runs/AFO-T001/latest.json |
| AFO-T002 | M0 | P0 | PASS | AT-065, AT-066 | evidence/v0.4/runs/AFO-T002/latest.json |
| AFO-T003 | M0 | P0 | PASS | AT-063, AT-064, AT-065 | evidence/v0.4/runs/AFO-T003/latest.json |
| AFO-T004 | M0 | P0 | PASS | AT-063, AT-064, AT-065, AT-066 | evidence/v0.4/runs/AFO-T004/latest.json |
| AFO-T005 | M0 | P0 | PASS | AT-030, AT-045, AT-046 | evidence/v0.4/runs/AFO-T005/latest.json |
| AFO-T006 | M0 | P0 | PASS | AT-063, AT-064 | evidence/v0.4/runs/AFO-T006/latest.json |
| AFO-T007 | M1 | P0 | PASS | AT-001, AT-004, AT-005, AT-007 | evidence/v0.4/runs/AFO-T007/latest.json |
| AFO-T008 | M1 | P0 | PASS | AT-001, AT-003, AT-004, AT-005, AT-007, AT-009 | evidence/v0.4/runs/AFO-T008/latest.json |
| AFO-T009 | M1 | P0 | PASS | AT-001, AT-004, AT-005, AT-007 | evidence/v0.4/runs/AFO-T009/latest.json |
| AFO-T010 | M1 | P0 | PASS | AT-006 | evidence/v0.4/runs/AFO-T010/latest.json |
| AFO-T011 | M1 | P0 | PASS | AT-002, AT-008, AT-045, AT-046 | evidence/v0.4/runs/AFO-T011/latest.json |
| AFO-T012 | M1 | P0 | PASS | AT-003, AT-009 | evidence/v0.4/runs/AFO-T012/latest.json |
| AFO-T013 | M1 | P0 | PASS | AT-003, AT-005, AT-007, AT-009 | evidence/v0.4/runs/AFO-T013/latest.json |
| AFO-T014 | M1 | P0 | PARTIAL | AT-001, AT-004, AT-005, AT-007 | evidence/v0.4/runs/AFO-T014/latest.json |
| AFO-T015 | M1 | P0 | BLOCKED | AT-002, AT-008 | real reboot / mount-removal drill needs owner authorization and a maintenance window; also the data volume is a login-time udisks loop mount of an image on a removable exFAT drive, so a headless reboot cannot pass until the operator configures boot-time mounting (docs/afo/OPERATIONS-AFO.md section 2) Owner decision 2026-10-19: kept BLOCKED, restart/reboot drills deferred to later. |
| AFO-T016 | M2 | P0 | PASS | AT-011, AT-013, AT-015 | evidence/v0.4/runs/AFO-T016/latest.json |
| AFO-T017 | M2 | P0 | PASS | AT-010, AT-011, AT-012, AT-013 | evidence/v0.4/runs/AFO-T017/latest.json |
| AFO-T018 | M2 | P0 | PASS | AT-011, AT-013, AT-015, AT-066 | evidence/v0.4/runs/AFO-T018/latest.json |
| AFO-T019 | M2 | P0 | PASS | AT-011, AT-013, AT-021 | evidence/v0.4/runs/AFO-T019/latest.json |
| AFO-T020 | M2 | P0 | PASS | AT-014, AT-015, AT-016 | evidence/v0.4/runs/AFO-T020/latest.json |
| AFO-T021 | M2 | P0 | PASS | AT-004, AT-005, AT-007, AT-010, AT-014, AT-015 | evidence/v0.4/runs/AFO-T021/latest.json |
| AFO-T022 | M2 | P0 | PASS | AT-010, AT-012, AT-014 | evidence/v0.4/runs/AFO-T022/latest.json |
| AFO-T023 | M2 | P0 | PASS | AT-011, AT-012, AT-013, AT-014, AT-053, AT-054 | evidence/v0.4/runs/AFO-T023/latest.json |
| AFO-T024 | M2 | P0 | PASS | AT-013, AT-016, AT-021 | evidence/v0.4/runs/AFO-T024/latest.json |
| AFO-T025 | M2 | P0 | PASS | AT-021, AT-041 | evidence/v0.4/runs/AFO-T025/latest.json |
| AFO-T026 | M3 | P0 | PASS | AT-018, AT-019 | evidence/v0.4/runs/AFO-T026/latest.json |
| AFO-T027 | M3 | P0 | PASS | AT-017, AT-018, AT-019, AT-025 | evidence/v0.4/runs/AFO-T027/latest.json |
| AFO-T028 | M3 | P0 | PASS | AT-017, AT-018, AT-019, AT-020, AT-025 | evidence/v0.4/runs/AFO-T028/latest.json |
| AFO-T029 | M3 | P0 | PASS | AT-018, AT-019, AT-020, AT-022 | evidence/v0.4/runs/AFO-T029/latest.json |
| AFO-T030 | M3 | P0 | PASS | AT-022, AT-023 | evidence/v0.4/runs/AFO-T030/latest.json |
| AFO-T031 | M3 | P0 | PASS | AT-022, AT-023, AT-024 | evidence/v0.4/runs/AFO-T031/latest.json |
| AFO-T032 | M3 | P0 | PASS | AT-024, AT-037, AT-057 | evidence/v0.4/runs/AFO-T032/latest.json |
| AFO-T033 | M3 | P0 | PASS | AT-017, AT-022, AT-024, AT-025, AT-037, AT-057 | evidence/v0.4/runs/AFO-T033/latest.json |
| AFO-T034 | M3 | P0 | BLOCKED | AT-019, AT-021, AT-022, AT-041 | real machine reboot with an in-flight Fabro run needs owner authorization and a maintenance window; also blocked by the login-time data-volume mount (docs/afo/OPERATIONS-AFO.md section 2). Crash windows are covered with a fake Fabro (AFO-T033) and label adoption against the live Fabro listing (AFO-T026) Owner decision 2026-10-19: kept BLOCKED, restart/reboot drills deferred to later. |
| AFO-T035 | M4 | P0 | PASS | AT-026, AT-027, AT-035, AT-036, AT-043 | evidence/v0.4/runs/AFO-T035/latest.json |
| AFO-T036 | M4 | P0 | PASS | AT-026, AT-028, AT-033, AT-035, AT-043 | evidence/v0.4/runs/AFO-T036/latest.json |
| AFO-T037 | M4 | P0 | PASS | AT-029 | evidence/v0.4/runs/AFO-T037/latest.json |
| AFO-T038 | M4 | P0 | PASS | AT-030, AT-036, AT-045, AT-046 | evidence/v0.4/runs/AFO-T038/latest.json |
| AFO-T039 | M4 | P0 | PASS | AT-031, AT-032, AT-033, AT-035, AT-036 | evidence/v0.4/runs/AFO-T039/latest.json |
| AFO-T040 | M4 | P0 | PASS | AT-023, AT-031, AT-032, AT-033 | evidence/v0.4/runs/AFO-T040/latest.json |
| AFO-T041 | M4 | P0 | PASS | AT-034 | evidence/v0.4/runs/AFO-T041/latest.json |
| AFO-T042 | M4 | P0 | PASS | AT-028, AT-033, AT-034 | evidence/v0.4/runs/AFO-T042/latest.json |
| AFO-T043 | M4 | P0 | PASS | AT-023, AT-031, AT-032 | evidence/v0.4/runs/AFO-T043/latest.json |
| AFO-T044 | M4 | P0 | PARTIAL | AT-035, AT-036 | evidence/v0.4/runs/AFO-T044/latest.json |
| AFO-T045 | M5 | P1 | PASS | AT-030, AT-043, AT-045, AT-046 | evidence/v0.4/runs/AFO-T045/latest.json |
| AFO-T046 | M5 | P1 | PASS | AT-043, AT-045, AT-046 | evidence/v0.4/runs/AFO-T046/latest.json |
| AFO-T047 | M5 | P1 | PASS | AT-044 | evidence/v0.4/runs/AFO-T047/latest.json |
| AFO-T048 | M5 | P1 | PASS | AT-045, AT-047, AT-048, AT-049 | evidence/v0.4/runs/AFO-T048/latest.json |
| AFO-T049 | M5 | P1 | PASS | AT-049 | evidence/v0.4/runs/AFO-T049/latest.json |
| AFO-T050 | M5 | P0 | PASS | AT-045, AT-047, AT-048, AT-049, AT-051 | evidence/v0.4/runs/AFO-T050/latest.json |
| AFO-T051 | M5 | P1 | PASS | AT-039, AT-047, AT-048, AT-050 | evidence/v0.4/runs/AFO-T051/latest.json |
| AFO-T052 | M5 | P1 | PASS | AT-048, AT-051 | evidence/v0.4/runs/AFO-T052/latest.json |
| AFO-T053 | M5 | P1 | PASS | AT-039, AT-050 | evidence/v0.4/runs/AFO-T053/latest.json |
| AFO-T054 | M6 | P0 | NOT_RUN | AT-037, AT-038, AT-039, AT-040 |  |
| AFO-T055 | M6 | P0 | NOT_RUN | AT-037, AT-038, AT-040, AT-042 |  |
| AFO-T056 | M6 | P0 | NOT_RUN | AT-052, AT-053, AT-054, AT-055 |  |
| AFO-T057 | M6 | P0 | NOT_RUN | AT-042, AT-052, AT-055 |  |
| AFO-T058 | M6 | P0 | NOT_RUN | AT-014, AT-053, AT-054 |  |
| AFO-T059 | M6 | P0 | NOT_RUN | AT-037, AT-056 |  |
| AFO-T060 | M6 | P0 | NOT_RUN | AT-037, AT-038, AT-039 |  |
| AFO-T061 | M6 | P0 | NOT_RUN | AT-042, AT-055 |  |
| AFO-T062 | M7 | P0 | NOT_RUN | AT-037, AT-057, AT-058 |  |
| AFO-T063 | M7 | P0 | NOT_RUN | AT-057, AT-058 |  |
| AFO-T064 | M7 | P0 | NOT_RUN | AT-059, AT-062, AT-063 |  |
| AFO-T065 | M7 | P0 | NOT_RUN | AT-060, AT-061 |  |
| AFO-T066 | M7 | P0 | NOT_RUN | AT-059, AT-063 |  |
| AFO-T067 | M7 | P0 | NOT_RUN | AT-062 |  |
| AFO-T068 | M7 | P0 | NOT_RUN | AT-062 |  |
| AFO-T069 | M7 | P0 | NOT_RUN | AT-054, AT-059, AT-062, AT-063, AT-064 |  |
| AFO-T070 | M7 | P0 | NOT_RUN | AT-054, AT-063, AT-064, AT-065, AT-066 |  |
| AFO-T071 | M8 | P0 | NOT_RUN | AT-064, AT-065 |  |
| AFO-T072 | M8 | P0 | NOT_RUN | AT-065, AT-066 |  |
| AFO-T073 | M8 | P0 | NOT_RUN | AT-037, AT-056 |  |
| AFO-T074 | M8 | P0 | NOT_RUN | AT-059, AT-062, AT-063 |  |
| AFO-T075 | M8 | P0 | NOT_RUN | AT-065, AT-066 |  |

| FR | P | Coverage | Tasks |
|---|---|---|---|
| AFO-FR-001 | P0 | PARTIAL | AFO-T001=PASS, AFO-T002=PASS, AFO-T075=NOT_RUN |
| AFO-FR-002 | P0 | PARTIAL | AFO-T003=PASS, AFO-T004=PASS, AFO-T071=NOT_RUN |
| AFO-FR-003 | P0 | COVERED | AFO-T004=PASS, AFO-T006=PASS |
| AFO-FR-004 | P0 | COVERED | AFO-T003=PASS, AFO-T004=PASS |
| AFO-FR-005 | P0 | PARTIAL | AFO-T001=PASS, AFO-T071=NOT_RUN |
| AFO-FR-006 | P0 | PARTIAL | AFO-T004=PASS, AFO-T018=PASS, AFO-T072=NOT_RUN |
| AFO-FR-007 | P0 | COVERED | AFO-T005=PASS, AFO-T038=PASS, AFO-T045=PASS |
| AFO-FR-008 | P0 | PARTIAL | AFO-T032=PASS, AFO-T062=NOT_RUN |
| AFO-FR-009 | P0 | PARTIAL | AFO-T007=PASS, AFO-T008=PASS, AFO-T009=PASS, AFO-T014=PARTIAL |
| AFO-FR-010 | P0 | COVERED | AFO-T008=PASS, AFO-T012=PASS, AFO-T013=PASS |
| AFO-FR-011 | P0 | COVERED | AFO-T010=PASS |
| AFO-FR-012 | P0 | PARTIAL | AFO-T011=PASS, AFO-T015=BLOCKED |
| AFO-FR-013 | P0 | COVERED | AFO-T007=PASS, AFO-T008=PASS, AFO-T021=PASS |
| AFO-FR-014 | P0 | COVERED | AFO-T012=PASS, AFO-T013=PASS |
| AFO-FR-015 | P0 | COVERED | AFO-T013=PASS, AFO-T021=PASS |
| AFO-FR-016 | P1 | COVERED | AFO-T011=PASS, AFO-T045=PASS |
| AFO-FR-017 | P0 | COVERED | AFO-T017=PASS, AFO-T022=PASS |
| AFO-FR-018 | P0 | COVERED | AFO-T017=PASS, AFO-T023=PASS |
| AFO-FR-019 | P0 | COVERED | AFO-T016=PASS, AFO-T018=PASS |
| AFO-FR-020 | P0 | COVERED | AFO-T020=PASS, AFO-T022=PASS |
| AFO-FR-021 | P0 | COVERED | AFO-T021=PASS, AFO-T022=PASS |
| AFO-FR-022 | P0 | COVERED | AFO-T016=PASS, AFO-T019=PASS |
| AFO-FR-023 | P0 | COVERED | AFO-T019=PASS, AFO-T024=PASS |
| AFO-FR-024 | P0 | COVERED | AFO-T020=PASS, AFO-T021=PASS |
| AFO-FR-025 | P1 | COVERED | AFO-T020=PASS, AFO-T024=PASS |
| AFO-FR-026 | P1 | PARTIAL | AFO-T023=PASS, AFO-T058=NOT_RUN |
| AFO-FR-027 | P0 | COVERED | AFO-T027=PASS, AFO-T028=PASS |
| AFO-FR-028 | P0 | COVERED | AFO-T026=PASS, AFO-T027=PASS, AFO-T028=PASS |
| AFO-FR-029 | P0 | COVERED | AFO-T028=PASS, AFO-T029=PASS |
| AFO-FR-030 | P0 | PARTIAL | AFO-T029=PASS, AFO-T034=BLOCKED |
| AFO-FR-031 | P0 | COVERED | AFO-T030=PASS, AFO-T031=PASS |
| AFO-FR-032 | P0 | COVERED | AFO-T030=PASS, AFO-T031=PASS |
| AFO-FR-033 | P0 | COVERED | AFO-T027=PASS, AFO-T028=PASS, AFO-T033=PASS |
| AFO-FR-034 | P0 | COVERED | AFO-T032=PASS, AFO-T033=PASS |
| AFO-FR-035 | P0 | COVERED | AFO-T031=PASS, AFO-T033=PASS |
| AFO-FR-036 | P1 | PARTIAL | AFO-T034=BLOCKED, AFO-T025=PASS |
| AFO-FR-037 | P0 | COVERED | AFO-T035=PASS |
| AFO-FR-038 | P0 | COVERED | AFO-T035=PASS, AFO-T036=PASS |
| AFO-FR-039 | P0 | COVERED | AFO-T036=PASS, AFO-T042=PASS |
| AFO-FR-040 | P0 | COVERED | AFO-T037=PASS |
| AFO-FR-041 | P0 | COVERED | AFO-T038=PASS |
| AFO-FR-042 | P0 | COVERED | AFO-T039=PASS, AFO-T040=PASS |
| AFO-FR-043 | P0 | COVERED | AFO-T040=PASS, AFO-T043=PASS |
| AFO-FR-044 | P0 | COVERED | AFO-T036=PASS, AFO-T042=PASS |
| AFO-FR-045 | P0 | COVERED | AFO-T041=PASS, AFO-T042=PASS |
| AFO-FR-046 | P0 | PARTIAL | AFO-T035=PASS, AFO-T039=PASS, AFO-T044=PARTIAL |
| AFO-FR-047 | P0 | COVERED | AFO-T040=PASS, AFO-T043=PASS |
| AFO-FR-048 | P1 | PARTIAL | AFO-T038=PASS, AFO-T039=PASS, AFO-T044=PARTIAL |
| AFO-FR-049 | P0 | COVERED | AFO-T045=PASS, AFO-T046=PASS |
| AFO-FR-050 | P1 | COVERED | AFO-T045=PASS, AFO-T046=PASS |
| AFO-FR-051 | P1 | COVERED | AFO-T047=PASS |
| AFO-FR-052 | P1 | COVERED | AFO-T048=PASS, AFO-T051=PASS |
| AFO-FR-053 | P0 | COVERED | AFO-T048=PASS, AFO-T050=PASS |
| AFO-FR-054 | P1 | COVERED | AFO-T049=PASS |
| AFO-FR-055 | P1 | COVERED | AFO-T050=PASS, AFO-T052=PASS |
| AFO-FR-056 | P0 | COVERED | AFO-T051=PASS, AFO-T053=PASS |
| AFO-FR-057 | P1 | COVERED | AFO-T051=PASS, AFO-T053=PASS |
| AFO-FR-058 | P0 | OPEN | AFO-T054=NOT_RUN, AFO-T060=NOT_RUN |
| AFO-FR-059 | P0 | OPEN | AFO-T054=NOT_RUN, AFO-T055=NOT_RUN |
| AFO-FR-060 | P0 | OPEN | AFO-T055=NOT_RUN |
| AFO-FR-061 | P1 | OPEN | AFO-T056=NOT_RUN, AFO-T057=NOT_RUN |
| AFO-FR-062 | P1 | OPEN | AFO-T056=NOT_RUN, AFO-T058=NOT_RUN |
| AFO-FR-063 | P0 | OPEN | AFO-T057=NOT_RUN, AFO-T061=NOT_RUN |
| AFO-FR-064 | P0 | OPEN | AFO-T059=NOT_RUN, AFO-T073=NOT_RUN |
| AFO-FR-065 | P0 | OPEN | AFO-T062=NOT_RUN, AFO-T063=NOT_RUN |
| AFO-FR-066 | P0 | OPEN | AFO-T062=NOT_RUN, AFO-T063=NOT_RUN |
| AFO-FR-067 | P0 | OPEN | AFO-T064=NOT_RUN, AFO-T066=NOT_RUN |
| AFO-FR-068 | P0 | OPEN | AFO-T065=NOT_RUN |
| AFO-FR-069 | P1 | OPEN | AFO-T067=NOT_RUN, AFO-T068=NOT_RUN |
| AFO-FR-070 | P0 | OPEN | AFO-T064=NOT_RUN, AFO-T069=NOT_RUN, AFO-T074=NOT_RUN |
| AFO-FR-071 | P0 | OPEN | AFO-T070=NOT_RUN, AFO-T072=NOT_RUN, AFO-T075=NOT_RUN |
| AFO-FR-072 | P0 | OPEN | AFO-T069=NOT_RUN, AFO-T070=NOT_RUN |
