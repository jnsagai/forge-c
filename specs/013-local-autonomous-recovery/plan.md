# Implementation and validation plan

1. Reuse the existing AFO planner, Maintainer, signed authority, queue, native
   Fabro client, MCP ticket enforcement and CRE evaluator.
2. Add durable local-agent jobs, asynchronous native Fabro dispatch/polling and
   a separate deterministic candidate-verification worker. Admit only pinned,
   explicitly selected local profiles and authorized models.
3. Complete the AFO overlay in native authorization/preflight, correct admission
   routing, and provide bounded paged tool data with authoritative case identities.
4. Propagate validated recovery context through outbox, launcher, native author
   prompts and structured packets, preserving input hashes and independence.
5. Run targeted new cases, inherited AFO/work-order/local-runtime/policy tests,
   static design checks, provenance scan and independent CRE CHANGE evaluation.
6. Publish a draft review and prepare unsigned owner activation files. Do not
   modify the remote pinned run, auto-merge source, forge a signature or launch
   another GPU test. Record live activation as pending until actually authorized.
