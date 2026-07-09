# Pillar 4 — Security Review

## Audit Results
- **Data Isolation**: Verified. State relies on Pipecat session context; no global state leakage in `tts_factory`.
- **Session Isolation**: Verified. `metadata` overrides are injected locally per session.
- **Concurrency**: Verified.
- **Race Conditions**: None found.
- **Mutable Shared State**: None. Only immutable config is imported.
- **Thread Safety**: Verified.
- **Input Validation**: Verified. Early config validation prevents API keys from being leaked as missing or malformed inputs.
- **Exception Leakage**: Verified. Graceful handling, raising distinct `ValueError`s.
