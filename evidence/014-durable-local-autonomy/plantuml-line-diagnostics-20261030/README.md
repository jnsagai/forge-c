# Bounded PlantUML source-line feedback

This extends the canonical-view diagnostics in `cad31b1b`. The pinned
PlantUML1.2026.8 CLI's `-checkonly` returns a generic failure; `-syntax` with
stdin returns an ERROR marker, a zero-based line and a parser message. A real
local fixture established that line3 maps to source line4. The jar digest and
actual invocation results are retained. No Qwen inference or Qwen-generated
artifact was tested locally.

After a canonical file fails its original syntax check, the checker may obtain
this extra diagnostic with a15-second timeout. It reports the file and line
without replacing the original FAIL. Missing, malformed, successful or
out-of-range diagnostic output and diagnostic timeouts retain the original
failure. The normal valid-view and rendering path is unchanged. No quality or
release condition is waived.

The new source-line regression failed before this change (3PASS/1FAIL).
An intermediate run exposed two test assertions that excluded the new
syntax-only diagnostic invocation; these were updated to continue excluding
rendering after a syntax failure. That failed receipt is preserved. Final
focused tests:10PASS, including a real pinned-CLI broken-view location.
Inherited architecture/MCP/delivery cohort:63PASS/one disabled live Fabro skip,
zero failures/errors. Counts overlap and must not be added. Ruff/diff checks
and specification validation PASS; the latter is not runtime qualification.

```text
python -m pytest factory/python/tests/test_plantuml_diagnostics.py factory/python/tests/test_reqif_plantuml.py -q
python -m pytest factory/python/tests/test_plantuml_diagnostics.py factory/python/tests/test_reqif_plantuml.py factory/python/tests/test_swe2_architecture.py factory/python/tests/test_m2_mcp.py factory/python/tests/test_pipeline_demonstration.py factory/python/tests/test_delivery_first.py -q
```

The actual AFO run remains untouched at clean `a34fdd85`. This change is
**NOT_DEPLOYED / MODEL_BENEFIT_NOT_MEASURED**. The active run reached SWE.3
inspection at23:29:40UTC; terminal DF-M1 and the three fresh trials remain
pending. Exact clean implementation revision
**2d6b1bcfda29fe40a1f640ba042f89f6509d780f** repeated the broader cohort:
63PASS/one disabled live Fabro skip, zero failures/errors; see
[tested revision](tested-revision.json) and [JUnit receipt](exact.xml).

Raw failed-test JUnit text included trailing spaces that failed the publication
diff check. The readable `before.xml` and `intermediate.xml` views now omit only
that whitespace; exact originals are losslessly retained as adjacent `.gz`
files and locally. [Representation hashes](receipt-representations.json) bind
both forms and preserve the original failed results/test counts.
