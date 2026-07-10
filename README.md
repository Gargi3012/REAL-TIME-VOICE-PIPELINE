# Real-Time Voice Pipeline

[![Python](https://img.shields.io/badge/Python-3.14%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com)
[![Pipecat](https://img.shields.io/badge/Pipecat-1.5.0-orange)](https://pipecat.ai)

## 1. Project Overview
This project is a **real-time conversational AI voice assistant backend** built around a highly modular, decoupled architecture. 

It provides an orchestration framework capable of handling streaming audio and bridging state-of-the-art AI models with zero-latency overhead. The core system manages complex conversation lifecycles, event dispatching, and error recovery natively.

**The system currently integrates:**
- Session Management
- Conversation State Machine
- Event Bus
- Pipeline Builder & Runner
- Pipecat Runtime
- LiveKit Transport
- Twilio Telephony Transport
- Deepgram STT
- Groq LLM
- ElevenLabs / Cartesia TTS

*(Note: Prior WebRTC integrations such as Daily have been migrated exclusively to LiveKit).*

## 2. Architecture Diagram

```text
       User
         │
         ▼
     Transport
 (LiveKit / Twilio)
         │
         ▼
    Deepgram STT
         │
         ▼
 Conversation Pipeline
(Session → FSM → EventBus → Pipeline Runner)
         │
         ▼
        LLM
(Groq / OpenAI / Gemini)
         │
         ▼
        TTS
(ElevenLabs / Cartesia)
         │
         ▼
   Audio Response
```

## 3. Features

- **Real-time voice conversations**: Zero-perceptible latency streaming.
- **Multi-session support**: Fully isolated, thread-safe session concurrency.
- **Event-driven architecture**: Asynchronous pub/sub event bus.
- **Finite State Machine**: Strict lifecycle state guarantees.
- **Pipeline orchestration**: Directed acyclic graph (DAG) builder and runner.
- **Provider abstraction**: Loose coupling between orchestrator and AI services.
- **LiveKit transport**: Full WebRTC support for browser/client clients.
- **Twilio telephony**: Production-ready inbound phone call routing via WebSockets.
- **Streaming STT**: Word-level continuous transcription.
- **Modular TTS**: Byte-streaming synthesized audio playback.
- **Conversation context**: Long-running conversation awareness.
- **Clean Architecture**: Strong boundary layers and dependency inversion.
- **Strong test coverage**: 430+ passing unit and integration tests.

## 4. Repository Structure

- `app/session/`: Core session lifecycle, context memory, and thread-safe data access.
- `app/conversation/`: The finite state machine mapping each voice transition.
- `app/events/`: Asynchronous publisher/subscriber backbone.
- `app/pipeline/`: Topology builder and execution runner for the components DAG.
- `app/adapters/pipecat/`: Bridge integrating the pipeline runner with the Pipecat framework.
- `benchmarks/`: Tooling for runtime latency and throughput measurements.
- `tests/`: Extensive pytest suites across all core modules.
- `scripts/`: Tooling and standalone validation scripts.
- `reports/`: Audit, performance, and validation summaries.

## 5. Technology Stack

| Category | Technology |
| :--- | :--- |
| **Language** | Python 3.14+ |
| **Framework** | FastAPI |
| **Runtime** | Pipecat 1.5.0 |
| **Transport** | LiveKit, Twilio |
| **STT** | Deepgram |
| **LLM** | Groq |
| **TTS** | ElevenLabs / Cartesia |
| **Testing** | Pytest |
| **Type Checking** | Mypy |
| **Linting** | Ruff |

## 6. Current Architecture

- **Session Manager**: Maintains the state, context history, and metadata of all active users. Responsible for memory isolation.
- **Conversation FSM**: A finite state machine enforcing strict lifecycle rules (e.g., preventing audio playback while currently synthesizing).
- **Event Bus**: The nervous system of the app. Components broadcast and subscribe to strongly typed lifecycle events.
- **Pipeline Builder**: A DAG builder that allows programmatic insertion of custom processing layers.
- **Pipeline Runner**: Resolves the DAG topologically and triggers execution gracefully.
- **Pipecat Adapter Layer**: Decouples our custom architectural abstractions from the concrete `pipecat-ai` library.
- **Transport Layer**: The abstraction providing `LiveKit` (WebRTC) and `Twilio` (Telephony) input/output.
- **STT**: Transcribes real-time audio from the transport into text tokens.
- **LLM**: Interprets text and streams conversational responses.
- **TTS**: Converts LLM text tokens into streaming audio bytes.

## 7. Implemented Milestones

| Milestone | Status |
| :--- | :--- |
| Session Management | ✅ |
| Conversation FSM | ✅ |
| Event Bus | ✅ |
| Pipeline Builder | ✅ |
| Pipeline Runner | ✅ |
| Pipecat Adapter | ✅ |
| Provider Integration | ✅ |
| LiveKit Migration | ✅ |
| Twilio Transport | ✅ |
| TTS Integration | ✅ |
| Runtime Validation | ✅ |

## 8. Benchmark Summary

*Metrics derived from `benchmarks/` execution:*

- **Session Creation**: 0.014 ms
- **Session Lookup**: 0.0002 ms
- **Throughput**: ~74,821 ops/sec
- **Groq LLM Latency**: Measured accurately per network conditions.
- **ElevenLabs TTS Latency**: Measured accurately per network conditions.

## 9. Validation Summary

### ✅ Verified
- Unit tests
- Integration tests
- Runtime validation
- Live provider validation
- Static analysis

### ⏳ Pending
- Production-scale load testing
- Distributed deployment
- Horizontal scaling benchmarks

## 10. Getting Started

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd project
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
5. Run the application:
   ```bash
   python app/main.py
   ```

### Transport Configuration
The pipeline dynamically chooses the transport based on the `TRANSPORT_MODE` environment variable.
- For WebRTC testing: `TRANSPORT_MODE=livekit`
- For Telephony: `TRANSPORT_MODE=twilio`

## 11. Environment Variables

The `.env` file must contain the following keys to function properly:

```env
# Transport Mode
TRANSPORT_MODE=livekit  # or twilio

# LiveKit (WebRTC)
LIVEKIT_URL=wss://your-livekit-server.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Twilio (Telephony)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=...

# AI Services
DEEPGRAM_API_KEY=...
GROQ_API_KEY=...
ELEVEN_LABS_API_KEY=...
ELEVEN_LABS_VOICE_ID=...
```

## 12. Testing

The repository maintains strict quality controls. Run the following commands to validate local changes:

```bash
# Run unit and integration tests
pytest

# Enforce code style
ruff check .

# Strict static type checking
mypy --strict
```

To run performance benchmarks locally:
```bash
python benchmarks/benchmark_runner.py
```

## 13. Development Log

All implementation progress, architectural decisions, validation results, benchmarking, and milestone reports are maintained in [DEVLOG.md](DEVLOG.md).

## 14. Future Roadmap

- **Streaming response optimization**
- **Redis-backed session storage**
- **Production observability**
- **Containerization**
- **Kubernetes deployment**
- **Multi-agent orchestration**
- **Long-term memory**
- **Distributed scaling**

## 15. Contribution

We welcome pull requests. Please ensure that all contributions strictly adhere to our test coverage policies (no PRs with failing `pytest`, `ruff`, or `mypy` checks). Ensure new architectural decisions are logged in `DEVLOG.md`.

## 16. License

This project is licensed under the MIT License.
