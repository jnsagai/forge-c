# T083 regression: existing repo suites, main vs feat/023 (2026-11-22)

Both runs in fresh detached worktrees (no untracked local files), same host, same Python, PYTHONPATH cleared.
main = f6d6e526 (merge base of the branch); branch = 7c70980a. The branch changes nothing under factory/, tools/,
tests/ or config/ (`git diff --stat main...HEAD -- factory tools tests config` is empty).

| Suite | main | branch |
|---|---|---|
| tests/spec/validate_design.py | PASS 14 | PASS 14 |
| unittest discover -s tests | 16 OK | 16 OK |
| pytest factory/python/tests | 1115 passed, 130 skipped, 41 failed, 42 errors | 1115 passed, 130 skipped, 41 failed, 42 errors |

The failed and errored test ids are identical on both (83 lines, `diff` empty; list below). They are not caused by this
branch: they need reference inputs that are not tracked in git (for example a datasheet Markdown under
`examples/0002-arm_55_rcc_st/inputs/`), local model runs, or the simulator, which a fresh worktree does not have.
Verdict: no change in results (PASS for T083).

## Rerun before the tag (2026-11-23)

- **Worktree:** fresh detached at `cee8b943`, with the factory environment (`. scripts/forge-env.sh`, PYTHONPATH
  cleared).
- **What the branch changes outside the package and the feature folder:** the constitution, the root README, one
  website page, and the new `tools/hi_floor_line.py` with its test. Nothing under `factory/` or `config/`.

| Suite | Branch at cee8b943 |
|---|---|
| tests/spec/validate_design.py | PASS 14 |
| unittest discover -s tests | 19 OK (16 earlier plus the 3 new floor-line tests) |
| pytest factory/python/tests | 1115 passed, 130 skipped, 41 failed, 42 errors (exit 1) |

The 83 failing and erroring test ids are **identical** to the list below (`diff` is empty). Verdict: no change (PASS).

In this run pytest ended without its final count line, both times it was run. The counts above come from its
progress characters (`.` passed, `s` skipped, `F` failed, `E` error), which add up to the 1328 collected tests.

## Failed / errored test ids (identical on main and branch)

- ERROR factory/python/tests/test_brownfield_checklist.py::test_st_pilot_items_record_vendor_findings
- ERROR factory/python/tests/test_brownfield_checklist.py::test_st_pilot_vendor_register_mismatch_is_found
- ERROR factory/python/tests/test_brownfield_fix.py::test_a_defect_naming_another_file_does_not_open_this_one
- ERROR factory/python/tests/test_brownfield_fix.py::test_change_outside_the_scope_functions_is_refused
- ERROR factory/python/tests/test_brownfield_fix.py::test_change_report_links_the_fix_to_its_defect
- ERROR factory/python/tests/test_brownfield_fix.py::test_code_defect_found_at_swe2_is_claimed_at_swe3_entry
- ERROR factory/python/tests/test_brownfield_fix.py::test_trace_map_keeps_the_delivered_fingerprint_after_a_fix
- ERROR factory/python/tests/test_brownfield_fix.py::test_unlinked_change_is_a_mismatch
- ERROR factory/python/tests/test_brownfield_fix.py::test_write_window_opens_only_while_a_code_defect_is_in_fix
- ERROR factory/python/tests/test_brownfield_frozen.py::test_delivery_check_and_verify_nodes
- ERROR factory/python/tests/test_brownfield_frozen.py::test_frozen_code_defect_is_escalated_to_the_owner
- ERROR factory/python/tests/test_brownfield_frozen.py::test_frozen_delivered_code_cannot_be_written_by_any_role
- ERROR factory/python/tests/test_brownfield_frozen.py::test_package_findings_and_delivery_record
- ERROR factory/python/tests/test_brownfield_frozen.py::test_safety_drafts_are_marked_unsigned_and_claim_free
- ERROR factory/python/tests/test_brownfield_frozen.py::test_swtrace_uses_the_trace_map_for_delivered_code
- ERROR factory/python/tests/test_brownfield_frozen.py::test_trace_map_seed_and_check
- ERROR factory/python/tests/test_brownfield_frozen.py::test_verify_unchanged_then_mismatch
- ERROR factory/python/tests/test_brownfield_pilot.py::test_contract_calls_compile_against_the_vendor_headers
- ERROR factory/python/tests/test_brownfield_pilot.py::test_query_functions_allocated_in_any_table_column_are_not_findings
- ERROR factory/python/tests/test_brownfield_pilot.py::test_st_intake_resolves_the_scope_and_lists_the_rest
- ERROR factory/python/tests/test_brownfield_pilot.py::test_st_ll_conforms_to_the_independent_requirement_contract
- ERROR factory/python/tests/test_brownfield_pilot.py::test_vendor_function_names_count_as_allocated
- ERROR factory/python/tests/test_brownfield_st_host.py::test_header_only_delivery_gets_a_build_only_unit
- ERROR factory/python/tests/test_brownfield_st_host.py::test_rcc_model_set_clear_table_matches_rm0486
- ERROR factory/python/tests/test_brownfield_st_host.py::test_st_code_runs_on_the_renode_rcc_model
- ERROR factory/python/tests/test_brownfield_st_host.py::test_st_code_unit_tests_run_on_the_host_device_map
- ERROR factory/python/tests/test_cre_capa_057.py::test_capa057_st_delivery_swe3_all_passes_with_recorded_findings
- ERROR factory/python/tests/test_peripheral_assurance.py::test_bare_plantuml_declaration_is_declared
- ERROR factory/python/tests/test_peripheral_assurance.py::test_fidelity_rather_than[Integration ran on the host and on Renode.-False]
- ERROR factory/python/tests/test_peripheral_assurance.py::test_fidelity_rather_than[Renode checks key protection and update status, rather than proving those effects on silicon.-False]
- ERROR factory/python/tests/test_peripheral_assurance.py::test_fidelity_rather_than[The watchdog behaviour was verified on silicon rather than in simulation.-True]
- ERROR factory/python/tests/test_peripheral_assurance.py::test_iwdg_ll_boundary_is_not_claimed_not_applicable
- ERROR factory/python/tests/test_peripheral_assurance.py::test_iwdg_loop_bound_check_sees_iwdg_polls
- ERROR factory/python/tests/test_peripheral_assurance.py::test_iwdg_missing_header_is_not_a_pass
- ERROR factory/python/tests/test_peripheral_assurance.py::test_iwdg_model_texts
- ERROR factory/python/tests/test_peripheral_assurance.py::test_iwdg_oracle_finds_the_api_header
- ERROR factory/python/tests/test_peripheral_assurance.py::test_iwdg_register_semantics_are_measured_not_vacuous
- ERROR factory/python/tests/test_peripheral_assurance.py::test_iwdg_unit_test_verifiers_run
- ERROR factory/python/tests/test_peripheral_assurance.py::test_no_rcc_identifier_in_iwdg_verifier_reports
- ERROR factory/python/tests/test_peripheral_iwdg.py::test_iwdg_harness_and_implementation_check
- ERROR factory/python/tests/test_peripheral_iwdg.py::test_iwdg_register_map_is_generated_with_iwdg_names_only
- ERROR factory/python/tests/test_peripheral_iwdg.py::test_iwdg_robot_suite_header_and_observation_tokens
- FAILED factory/python/tests/test_brownfield_conformance.py::test_api_call_none_is_no_code_and_not_a_contract_error
- FAILED factory/python/tests/test_brownfield_conformance.py::test_each_seeded_mismatch_gives_its_finding_kind[extra_function]
- FAILED factory/python/tests/test_brownfield_conformance.py::test_each_seeded_mismatch_gives_its_finding_kind[missing_function]
- FAILED factory/python/tests/test_brownfield_conformance.py::test_each_seeded_mismatch_gives_its_finding_kind[overwritten_bit]
- FAILED factory/python/tests/test_brownfield_conformance.py::test_each_seeded_mismatch_gives_its_finding_kind[wrong_mask]
- FAILED factory/python/tests/test_brownfield_conformance.py::test_each_seeded_mismatch_gives_its_finding_kind[wrong_register]
- FAILED factory/python/tests/test_brownfield_conformance.py::test_inject_after_swe1_records_the_frozen_baseline
- FAILED factory/python/tests/test_brownfield_conformance.py::test_inject_refuses_a_tampered_store
- FAILED factory/python/tests/test_brownfield_conformance.py::test_inject_refuses_before_swe1_passes
- FAILED factory/python/tests/test_brownfield_conformance.py::test_requirement_authors_cannot_read_delivered_code
- FAILED factory/python/tests/test_brownfield_conformance.py::test_unmodified_delivery_is_conformant
- FAILED factory/python/tests/test_brownfield_fix.py::test_fix_allowed_contradiction_files_a_code_defect_in_fix_and_reworks
- FAILED factory/python/tests/test_brownfield_frozen.py::test_package_findings_when_never_injected
- FAILED factory/python/tests/test_brownfield_intake.py::test_build_failure_blocks_with_the_build_evidence
- FAILED factory/python/tests/test_brownfield_intake.py::test_functions_outside_the_scope_are_listed_as_excluded
- FAILED factory/python/tests/test_brownfield_intake.py::test_greenfield_prepare_is_unchanged
- FAILED factory/python/tests/test_brownfield_intake.py::test_intake_accepts_fingerprints_scopes_and_keeps_the_code_out_of_the_workspace
- FAILED factory/python/tests/test_brownfield_intake.py::test_intake_only_cli_and_blocked_cli
- FAILED factory/python/tests/test_brownfield_intake.py::test_intake_refusals_stop_before_any_workspace[<lambda>-DELIVERY_FILE_MISSING_OR_OUTSIDE_SOURCE:../../workorder.json]
- FAILED factory/python/tests/test_brownfield_intake.py::test_intake_refusals_stop_before_any_workspace[<lambda>-DELIVERY_LICENCE_MISSING]
- FAILED factory/python/tests/test_brownfield_intake.py::test_intake_refusals_stop_before_any_workspace[<lambda>-DELIVERY_MODE_FORBIDDEN_BY_LICENCE:FIX_ALLOWED]
- FAILED factory/python/tests/test_brownfield_intake.py::test_intake_refusals_stop_before_any_workspace[<lambda>-DELIVERY_ORIGIN_MISSING]
- FAILED factory/python/tests/test_brownfield_intake.py::test_intake_refusals_stop_before_any_workspace[<lambda>-DELIVERY_SCOPE_FUNCTION_NOT_FOUND:LL_RCC_PLL1_Enable]
- FAILED factory/python/tests/test_brownfield_intake.py::test_intake_refusals_stop_before_any_workspace[<lambda>-DELIVERY_SPEC_INVALID]
- FAILED factory/python/tests/test_cre_d7_e2e.py::test_latest_local_qwen_work_order_has_real_terminal_evidence
- FAILED factory/python/tests/test_kpi_003.py::test_kpi_t012_observer_mcp_read_only_and_least_privilege
- FAILED factory/python/tests/test_kpi_003.py::test_kpi_t020_pilot_reconciles_with_raw_evidence
- FAILED factory/python/tests/test_layer_split.py::test_capa044_owner_asil_scope_supersedes_the_example_qm_allocation
- FAILED factory/python/tests/test_layer_split.py::test_hal_prepare_requires_a_verified_ll
- FAILED factory/python/tests/test_layer_split.py::test_hal_refuses_a_provided_header_from_a_non_ll_work_order
- FAILED factory/python/tests/test_layer_split.py::test_ll_prepare_records_the_layer
- FAILED factory/python/tests/test_owner_safety_documents.py::test_prepare_copies_only_signed_documents_read_only
- FAILED factory/python/tests/test_peripheral_contract.py::test_oracle_checks_the_written_value
- FAILED factory/python/tests/test_peripheral_contract.py::test_write_effects_are_valid_contract_entries
- FAILED factory/python/tests/test_peripheral_hal.py::test_busy_contract_entries_are_validated
- FAILED factory/python/tests/test_peripheral_hal.py::test_oracle_on_an_iwdg_hal
- FAILED factory/python/tests/test_peripheral_iwdg.py::test_unknown_key_section_is_refused
- FAILED factory/python/tests/test_peripheral_rcc_equivalence.py::test_rcc_register_map_generation_unchanged
- FAILED factory/python/tests/test_peripheral_sim.py::test_iwdg_model_on_renode
- FAILED factory/python/tests/test_peripheral_sim.py::test_the_target_startup_enables_the_fpu
- FAILED factory/python/tests/test_t048_e2e.py::test_t048_unattended_local_qwen_run_and_reproducible_evidence
