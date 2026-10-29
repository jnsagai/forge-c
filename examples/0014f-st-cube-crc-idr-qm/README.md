# Owner-selected QM IDR development

Purpose **QM**, profile local-rtx-v2-omniverse2-q38-qm-mtp.
Uses the same frozen LL_CRC_Write_IDR / LL_CRC_Read_IDR scope and nine functional
requirements, including simulation-only64instructions/call and100µs/call at100MIPS.

The original nine-requirement functional payload was reviewed by the owner.
On29October the owner explicitly requested “Forget about safety now!!! implement
as QM”. The provided input preserves all functional content and sources; only its
scope identity changes. Its composite review retains the original full review and
links the actual QM reclassification record. No second full review is invented.

The existing generic QM scope/checklist/release mechanisms apply to any driver.
Only safety-specific criterion clauses are tailored; functional startup/error
contracts, architecture, resource budgets, trace, code quality and all required
verification still block on failure. Naming disposition OD-2026-10-25-01 applies
only to the identical frozen header covered by its existing owner approval.

Example preparation (zero model requests):
~~~sh
PYTHONPATH=factory/python python factory/qualification/014/prepare_reviewed_requirements.py \
  --purpose QM --model local-rtx-v2-omniverse2-q38-qm-mtp \
  --example examples/0014f-st-cube-crc-idr-qm \
  --state-root "$FC014_NEW_PRIVATE_STATE" --work-order WO-QM-IDR-UNIQUE \
  --out "$FC014_NEW_REPORT"
~~~
Use loop10 for workstation outputs and Omniverse2 for actual Qwen execution.
Real live inspection and a complete verified package are still required.
