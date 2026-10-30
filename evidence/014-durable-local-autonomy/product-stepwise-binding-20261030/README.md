# Signed product trial selects stepwise diagnosis before measurement

Source `a32d87a311cc4a46cd12b6f00d1aea8a210c305c` binds the independently signed
experimental product-role trial before its initial request is measured/reserved.
Previously, late binding meant product diagnosis still selected the one-response
schema. Each later request reauthenticates the trial and verifies its selected class.
Ambiguous classes, revocation, forged/unbound selectors and changed classes are
covered. Existing qualification and measured-role paths remain compatible.

The new `local-rtx-v2-omniverse2-q38-aspice-stepwise-medium` profile uses normal
blocking ASPICE gates and enables existing recovery, with no demo-policy deferral.
Q8/f16/MTP3/context262144/one inference remain. Its1M cumulative planner-job allowance
does not enlarge any individual request's physical context or reset mission charges.
It is an unqualified experimental configuration, not the active production profile.

Exact-source local148PASS, zero failures/errors/skips, [JUnit](local-148-junit.xml):

```sh
FORGE_FABRO_BIN=/home/jefferson/.fabro/bin/fabro \
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTHONPATH="$W/factory/python" FORGE_DATA_ROOT="$B" FORGE_FABRO_LIVE=0 TMPDIR="$A3" \
"$B/venv/bin/python" -m pytest -q -p no:cacheprovider \
 factory/python/tests/test_da014_product_role_trial.py \
 factory/python/tests/test_da014_role_envelopes.py \
 factory/python/tests/test_da014_two_step.py \
 factory/python/tests/test_da014_qualification_reservations.py \
 factory/python/tests/test_da014_protocol_faults.py \
 factory/python/tests/test_afo_local_autonomy.py
```

The preparation run117PASS overlaps this coverage. An earlier local attempt failed
because its ordering-test fixture omitted the launch file and the invocation omitted
FORGE_FABRO_BIN; raw private JUnit is retained in A3, not counted as passing. No model
request or production mutation occurred. Ruff and diff checks pass separately.

Native tools qualify a detached exact-source clone with actual authoritative input
fixtures,4CPUs/8GiB/no swap, separate verifier identity, no network/GPU/owner/SSH.
The window requires completed eight-case stepwise evidence, real execution/resource
quiescence and unchanged RUNNING98. It pauses99, then resumes only its own unchanged
pause after the verifier is quiescent. It never activates source or dispatches inference.
Original native WAL305/1 remains a separate failed run. Specification validation is
not runtime qualification. Formal Feature01430/58 unchanged; no task newly closed.

The native run completed: **333PASS**, zero failures/errors/skips,40.49pytest seconds,
source clean before/after. [Original native provenance, JUnit and log](native/qualification-product-stepwise-a32d87a3-epoch99-v1/)
and [window receipt](native/product-stepwise-qualification-window-epoch98-v1/result.json)
are hash-verified locally. Verifier quiescence confirmed; only own PAUSED99 resumed
to RUNNING100. Model requests0, source deployment false. Private XDG directory plus
read-only actual Ollama executable let the original systemd verification test pass
without exposing GPU/model weights or host credentials. Original305/1 run remains.
Spec/contracts and14design validations PASS separately, not runtime qualification.
