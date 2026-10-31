# Proposal (owner decision needed): SWE.1 completeness against the owner contract

**Measured (README.md here).** Ornith's attempt-2 SWE.1 baseline has no requirement for three obligations stated in
the CRC IDR owner contract: no status polling, no error code on a valid call, and preserving the other fields and
registers.
- **Author gate:** froze it.
- **Qwen inspector at medium:** passed it 8/8.
- **Qwen inspector at xhigh:** failed one item, for an unrelated reason (SWR-003 verifiability).

Neither inspector named any of the three.

**Cause (structural, not the model).**
1. **The contract is not visible.** The inspector's sources (`lrtx/review.evidence`) are the baseline files plus
   scope/budget and assessment-context views of the manifest. The owner contract (`IDR-CONTRACT.md`) and other
   declared owner inputs are not among them, so the preservation obligation is invisible to the inspector.
2. **No checklist item asks for completeness.** None of SWE1-01…06 asks "does every owner or scope obligation have a
   requirement?". SWE1-05 ("coverage gaps are recorded") is satisfied when the baseline records that its upstream
   inputs are not provided.
3. **The author gate checks structure only.** It does not compare requirements against the owner contract.

So more inspector reasoning effort cannot fix this. The xhigh run cost 644 s and still did not raise the omission.

**Options. These are complementary rather than exclusive; the owner chooses the scope.**

| Option | Mechanism | Path / authority | Trade-off |
|---|---|---|---|
| 1. Show the contract to the inspector | `lrtx/review.evidence` adds the work order's declared owner-contract and scope inputs as sources. | Factory code (CRE). | Lets the model judge completeness, but still relies on the model noticing. Larger packets. |
| 2. Add a completeness checklist item | A new SWE.1 item: every obligation stated in the owner contract or scope maps to at least one requirement, or to a recorded open point. | `factory/checklists/**` is a **protected path**, so this needs explicit owner approval and its own versioned checklist change. | Makes completeness an explicit inspection criterion; still judged by the model. |
| 3. Deterministic contract-coverage gate | The owner contract carries machine-readable obligations (ids plus matching keys, like the oracle predicates). The SWE.1 author gate refuses a baseline where an obligation has no covering requirement, or no recorded open point. | Factory code (CRE), plus a structured obligations block in the owner-contract input. | No model judgement; catches this case every time. Needs owners to state obligations in structured form; that format is the same work as the CRC oracle (Q4). |

**Recommendation:** 3 as the guarantee, plus 1 so the inspector can judge what the gate cannot express. 2 is
optional. The oracle (Q4) and option 3 share one obligation format, so the work is done once. Nothing has been
implemented yet.
