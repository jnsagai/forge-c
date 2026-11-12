# CHANGE gates 2026-11-01: gateway live tap and the process-lab signer line

- **Live tap** (10cd4ec3, owner 2026-11-01 "yes, proceed with answer tokens only"): display-only broadcast of the
  relayed answer tokens; reasoning is stripped before the tap; nothing is stored; opt-in per profile (think profile v3).
  pd-1853c5dbf3dddd4805cb ELIGIBLE (CHANGE vs its parent, oracle commit aef1b5fe).
- **Signer line** (e03eb022, owner 2026-11-01 "I approve it"): config/factory/process-lab-allowed-signers, the owner's
  public key for namespace forge-process-lab-disposition.
  - Gated at its own revision against 708d84e1: pd-1e6427454096ffc52877 REJECTED, prevention
    RESOLVED_FAILURE_REAPPEARED (RPR-087). That revision predates the CAPA-087 fix in history; the ordering, not the file,
    failed.
  - Gated at the current revision: candidate 10cd4ec3 against 1bfd26ec (branch gate/no-signer-base = 10cd4ec3 minus that
    one file, a gate baseline only): pd-fe69cc4cacdad44afb6b ELIGIBLE.
- **First attempt, a range gate** 708d84e1..10cd4ec3: pd-1274b60f539073dd4ad0 REJECTED, PROTECTED_PATH_CHANGE. The range
  included the CAPA-087 oracle commit. A CHANGE range must never span oracle commits.
- **Regression** (swap set plus test_gateway_live_tap, test_llm_gateway, test_lrtx_admission, test_same_item_stuck) at
  10cd4ec3 and at the baseline worktree: 1687 passed / 7 failed and 1679 passed / 7 failed. The same 7 tests fail on both
  sides (regression-failures-both-sides.txt). The baseline worktree stayed at e03eb022, not 708d84e1: a fast-forward to an
  ancestor is a no-op, and e03eb022 differs from 708d84e1 only by the signer config file.
- Eligible for OFFLINE review only. No deployment, no merge to main.
