# Pillar 4 — Scalability Review

## Evaluation
- **Horizontal Scaling**: Excellent. Completely stateless factory design. The lack of in-memory audio buffers on the factory layer means horizontal auto-scaling will not be hindered.
- **Dependency Injection**: Excellent. Uses metadata dictionaries heavily.
- **Provider Abstraction**: Strong. Confined to ElevenLabs now, but architecturally aligned with Pipecat, making provider rotation simple.
- **Transport Abstraction**: N/A for TTS layer directly.
- **Future Extensibility**: High.

## Agility
- **How difficult would it be to replace providers?**: Trivial. Replace the `ElevenLabsTTSService` return type with another Pipecat compatible service (e.g. `CartesiaTTSService`).
- **How difficult would it be to add providers?**: Easy. Can implement a simple switch case or factory registry.
- **How difficult would it be to add transports?**: Handled by Pillar 2.
- **How difficult would it be to add processors?**: Handled by Pillar 1 (Pipeline Builder).
