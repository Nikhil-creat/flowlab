# FlowLab: Security and Operational Limits

## Guarantees
- **Write-ahead log:** every transition is appended to `events` before its side effect. The table is append-only (trigger-enforced).
- **Idempotency:** key = `workflow_id:step_id:attempt`. Re-appends are no-ops; activities receive the key and must pass it to downstream APIs.
- **Replay:** a restarted worker rebuilds state from `STEP_COMPLETED` events and skips finished steps. A crash after `STEP_STARTED` re-runs only that step, with the same key.
- **Retries:** exponential backoff with jitter, a circuit breaker per activity, then agent remediation, then the DLQ.

## Security
| Area | Policy |
|---|---|
| AuthN/Z | OIDC + JWT (RS256, audience check). Roles: Viewer, Operator, Admin. The agent service fails closed without OIDC (`ENV=dev` only for local use). |
| Transit | TLS 1.3 for all hops in production (mesh mTLS, Kafka SSL listeners, gRPC). The bundled compose file uses a private network without TLS, for local development only. |
| At rest | AES-256-GCM field encryption of payloads (`FIELD_KEY_HEX`; use a KMS or secret manager in prod). |
| Input | JSON Schema / Zod validation on every trigger and activity payload. |
| Runtime | Non-root UID 10001, read-only root filesystem, `cap_drop: ALL`, `no-new-privileges`. |

## Known limits and defences
1. **Non-determinism:** workflow code must not read clocks, randomness or the network. Do that only inside activities.
2. **Replay lag:** consumers use bounded polls (`max_poll_records`) and manual commits so replays cannot starve live traffic. Add per-tenant rate limits in Redis.
3. **LLM variance:** temperature 0, fixed seed, schema-bound JSON. The Critic can veto, and destructive actions always need human approval (`HITL_REQUIRED`).
4. **Resources:** CNN workers are capped at 2 GiB / 1.5 CPU plus an in-process address-space limit, so an OOM stays contained.
5. **Reference model:** `cnn_worker.py` runs a generic ImageNet MobileNet. Fine-tune and validate it on your own data before trusting it for approvals.
