# Contract: the model channel

This is the only interface between the factory machine and a model service. It is the subset of the OpenAI-compatible HTTP API that any vLLM-class service offers, plus one **optional** Forge-C extension. The factory MUST work against a service that offers only the required part. The extension adds attestation; it is never a requirement.

## Transport

- HTTPS in production; plain HTTP is allowed only on the Omniverse2 internal container network.
- An internal CA bundle can be supplied by reference (`ca_bundle_ref`).
- `Authorization: Bearer <tenant key>` on every request. The key is never logged.

## Required endpoints

| Method and path | Factory use | Fields relied on |
| --- | --- | --- |
| `GET /v1/models` | Identity fallback and health | `data[].id`, `data[].max_model_len` (vLLM), `data[].root` |
| `POST /v1/chat/completions` | Every model call | Request: `model`, `messages`, `tools`, `tool_choice`, `max_tokens`, `temperature`, `stream`, `chat_template_kwargs.enable_thinking=false`. Response: `choices[].message.{content,tool_calls}`, `choices[].finish_reason`, `usage.{prompt_tokens,completion_tokens,prompt_tokens_details.cached_tokens}` |

## Optional Forge-C extension (the tenant gateway provides it; production may not)

| Item | Meaning |
| --- | --- |
| `GET /forge/v1/identity` | A `served-model-identity.schema.json` document with `attested: true` |
| Response header `x-forge-model-identity` | The first 16 hex characters of `revision_fingerprint`, on every chat response |
| Response header `x-forge-queue-ms` | Time the request waited for a slot |
| Error body `{"error": {"type": ..., "forge_reason": ...}}` | Machine reason for refusals (table below) |

## Status mapping (factory side, in both cases)

| Service answer | `forge_reason` (extension) | Factory reason | Factory behaviour |
| --- | --- | --- | --- |
| 401 / 403 | `credential_refused` | `credential_refused` | Incident; run BLOCKED; no retry |
| 429 | `share_exhausted` / `queue_timeout` | `share_exhausted` | Bounded wait (`queue_wait_max_s`), then BLOCKED; never a model failure |
| 400 | `context_exceeded` | `context_exceeded` | The factory should have refused before sending; recorded as a defect; the task is repartitioned |
| 409 | `identity_mismatch` | `identity_changed` | Run BLOCKED, naming both fingerprints |
| 5xx, connect error, TLS error | (none) | `service_unreachable` / `channel_interrupted` | Bounded outage wait (`outage_wait_max_s`), then BLOCKED or resume from the last quality-checked part |
| Connection lost after the request was sent | (none) | `outcome_unknown` | Recorded as unknown, never as success or zero cost |
| 200 with a different `x-forge-model-identity` | (none) | `identity_changed` | Run BLOCKED |
| 200 with a `reasoning_content` field | (none) | (counted) | Stripped before storage; above the threshold, infrastructure finding |

## Privacy guarantees of the service (Omniverse2 tenant gateway)

- No message, tool argument, content or reasoning is written to any log or file.
- Outcome records are metadata only (`data-model.md` OutcomeRecord).
- A tenant can never read another tenant's records. The gateway has no endpoint that returns records.
