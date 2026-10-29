# ◈ FlowLab

**AI-native, crash-proof workflow engine.** Event-sourced durable execution on PostgreSQL, Kafka and Redis, with agentic self-healing, CNN image inspection, RAG context and zero-trust security.

**Live site:** https://nikhil-creat.github.io/flowlab/

## Features
- Write-ahead event log, replay after crashes, idempotency key `workflow:step:attempt`
- Retries with backoff, circuit breakers, dead-letter queue
- Planner / Exec / Critic agents with human approval for destructive actions
- `CNN_IMAGE_INSPECTION` (ONNX) and `RAG_CONTEXT_FETCH` (pgvector) activities
- OIDC + RBAC, TLS 1.3, AES-256-GCM field encryption, non-root hardened containers
- Atlas-style site with live console, command palette (Ctrl/⌘ + K) and dark mode

## Run
Set `PG_PASSWORD`, `FIELD_KEY_HEX` (64 hex chars), `GROQ_API_KEY`; put a MobileNet ONNX file at `models/mobilenet.onnx`; then `docker compose up --build`.

## Docs
[SECURITY_AND_LIMITS.md](SECURITY_AND_LIMITS.md) · Built by [Nikhil Chary Sriramoju](https://github.com/Nikhil-creat)
