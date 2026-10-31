# Owner-obligation drafts

`forge-c/owner-obligations/1` documents for the SWE.1 owner-obligation coverage mechanism
(`../swe1-owner-obligation-coverage.md`). A work order uses one by declaring it as an input with role
`owner_obligations`.

| File | Work order | Status |
|---|---|---|
| `crc-idr-owner-obligations.json` | CRC IDR (`examples/0014g-st-crc-idr-qwen-delivery`, unchanged) | `DRAFT_FOR_OWNER_REVIEW` |

**CRC IDR draft (2026-10-31).** Each statement is the sentence of `IDR-CONTRACT.md` that states the obligation; the
contract's combined sentence "No startup accesses, status polling, allocation or setup occur in this scope" is split
into three obligations. Owner review points:

1. **`critical` marks are a proposal.** Write, read, preservation, no startup accesses and no polling are marked
   critical; allocation/setup, the no-error-code obligation and the out-of-domain statement are not.
2. **`OBL-no-error-code-valid-call` is derived**, not quoted: the contract states the signatures (`void` write,
   value-returning read) and that the caller supplies a valid accessible instance. It is one of the three obligations
   the Ornith a02 baseline omitted.
3. **`OBL-out-of-domain`** is a scope boundary. An author may cover it with a requirement or record it as an
   obligation gap with a reason; either satisfies the coverage gate.
4. **Effects:** only write and read carry register effects (`CRC_IDR.IDR`), so citing them requires a requirement
   with that effect.

The oracle (Q4) stays separate and hidden from the author.
