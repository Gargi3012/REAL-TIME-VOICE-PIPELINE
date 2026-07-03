# Developer Log — Real-Time Voice Pipeline

> **Project**: Real-Time Voice Pipeline (Project B)  
> **Pillar**: 1 — Pipecat Orchestration & State Management  
> **Author**: Rahul Manchanda  
> **Started**: 2026-07-01  

This file is an **append-only** architecture changelog.  
Each milestone is logged with date, scope, decisions, and outcomes.  
**Do not overwrite previous entries** — always append at the bottom.

---

## Project Progress Summary

> **Last Updated**: 2026-07-03 23:26 IST

### Milestones

| # | Milestone | Status | Package | Tests | Date |
|---|---|---|---|---|---|
| 1 | Session Management Layer | ✅ Complete | `app/session/` (5 files) | 166 | 2026-07-02 |
| 2 | Production Readiness Audit | ✅ Complete | `tests/` (8 files) | — | 2026-07-02 |
| 3 | Conversation State Machine | ✅ Complete | `app/conversation/` (6 files) | 146 | 2026-07-02 |
| 4 | Event Bus | ✅ Complete | `app/events/` (10 files) | 30 | 2026-07-02 |
| 5 | Pipeline Builder | ✅ Complete | `app/pipeline/` (9 files) | 25 | 2026-07-03 |
| 6 | Pipeline Runner | ✅ Complete | `app/pipeline/` (+6 files) | 18 | 2026-07-03 |
| 7 | Pipecat Adapter Integration | 🔲 Planned | `app/pipecat/` | — | — |

### Current Metrics

| Metric | Value |
|---|---|
| Total source files | 37 (`session/` 5 + `conversation/` 6 + `events/` 10 + `pipeline/` 16) |
| Total statements | 1184 |
| Total tests | 385 (all passing) |
| Line coverage | >94% |
| Branch coverage | >94% |
| Ruff | ✅ Clean |
| Mypy (strict) | ✅ Clean |

### Git History

| Commit | Message | Files |
|---|---|---|
| `09f8b46` | feat: pipeline runner execution engine | 21 changed |
| `4f34101` | feat: pipeline builder — immutable DAG orchestrator | 18 changed |
| `c3918c0` | feat: event bus implementation | 16 changed |
| `0772b50` | feat: conversation state machine | 12 changed |
| `1a465e5` | feat: session management layer + audit suite | 20 changed |

**Branch**: `feature/session-management` → `origin/feature/session-management`

---

## Milestone 1 — Session Management Layer

**Date**: 2026-07-02  
**Status**: ✅ Complete  
**Scope**: `app/session/` — Core session lifecycle and conversation state management

### What Was Built

| File | Purpose |
|---|---|
| `state.py` | `SessionState` enum — 6 states (IDLE → LISTENING → THINKING → SPEAKING → INTERRUPTED → CLOSED) with `is_active()` / `is_terminal()` helpers |
| `message.py` | Frozen `Message` dataclass — immutable, validated, LLM-API-compatible `to_dict()` |
| `models.py` | Mutable `Session` dataclass — UUID, timestamps, history, speaking flags, metadata, latency |
| `manager.py` | `SessionManager` — thread-safe CRUD, conversation ops, state transitions, Loguru logging |
| `__init__.py` | Package API surface with `__all__` exports |

### Key Design Decisions

1. **`Literal["system", "user", "assistant"]` for Role** — Serializes directly to LLM chat-completion format without `.value` calls. Chose Literal over Enum deliberately.

2. **`frozen=True` on Message, mutable Session** — Messages are immutable once created (thread-safe, referentially stable). Sessions are mutable because state, history, and flags change continuously during a live conversation.

3. **`slots=True` on both dataclasses** — ~20% memory reduction and faster attribute access. Acceptable trade-off since neither class needs `__dict__`.

4. **`threading.Lock` (not `asyncio.Lock`)** — Sufficient for multi-threaded ASGI servers. Designed to be swappable when going fully async.

5. **`Optional[Session]` returns over exceptions** — Caller decides error policy. Manager logs warnings for missing sessions but doesn't force exception handling.

6. **In-memory `dict` store** — Zero-dependency for development. Clean public API designed so the backing store can swap to Redis/PostgreSQL without changing callers.

7. **`metadata` + `latency` extension dicts** — Open extension points for Pipecat context, user profiles, and per-component timing metrics.

### Architecture Diagram

```
app/session/
├── state.py        ← SessionState enum (no deps)
├── message.py      ← Message dataclass (no deps)  
├── models.py       ← Session dataclass (imports message, state)
├── manager.py      ← SessionManager (imports all above + loguru)
└── __init__.py     ← Re-exports public API
```

Dependency flow: `state.py` ← `message.py` ← `models.py` ← `manager.py`  
No circular dependencies. Each file has a single responsibility.

---

## Milestone 2 — Production Readiness Audit & Test Suite

**Date**: 2026-07-02  
**Status**: ✅ Complete  
**Scope**: `tests/` — Exhaustive pytest suite + static analysis + code review

### Test Suite Delivered

| File | Tests | Category |
|---|---|---|
| `test_state.py` | 17 | Enum membership, is_active, is_terminal, identity |
| `test_message.py` | 30 | Validation, immutability, serialization, Unicode, hashability |
| `test_models.py` | 14 | Defaults, properties, touch, JSON serialization |
| `test_manager.py` | 38 | Full CRUD, conversation, state machine, activity tracking |
| `test_edge_cases.py` | 28 | Invalid IDs, post-deletion ops, bulk CRUD, ordering |
| `test_thread_safety.py` | 4 | Concurrent creates, deletes, messages, mixed ops |
| `test_serialization.py` | 8 | JSON roundtrip for Message + Session |
| `test_performance.py` | 9 | Benchmarks at 100/1K/10K + memory leak detection |
| **Total** | **166** | **All passing** |

### Quality Metrics

| Metric | Result |
|---|---|
| Tests | 166/166 passed (1.78s) |
| Line coverage | 100% |
| Branch coverage | 100% |
| Ruff | Clean |
| Mypy (strict) | Clean |
| Memory leaks | None detected (5K cycles) |

### Issues Found & Fixed

| # | Tool | Issue | Fix Applied |
|---|---|---|---|
| 1 | Ruff | Unused `datetime`, `timezone` imports in `manager.py` | Removed |
| 2 | Mypy | `dict` missing type args in `models.py:to_dict()` | Changed to `dict[str, object]` |

### Known Non-Blocking Issues

1. **TOCTOU in lock pattern** — `add_message()`, `clear_history()`, `set_state()`, `update_last_activity()` acquire the lock to look up the session, release it, then re-acquire to mutate. Between the two lock scopes another thread could delete the session. Impact: low (orphaned writes to deleted session objects, no crashes or corruption). **Fix when**: adding WebSocket concurrency.

2. **No abstract `SessionStore` interface** — Manager directly uses `dict`. Extracting a `Protocol`/ABC would formalize the Redis/DB swap path. **Fix when**: implementing Redis backend.

3. **No session TTL / auto-cleanup** — Idle sessions accumulate indefinitely. **Fix when**: adding background task infrastructure.

4. **No state transition validation matrix** — Any non-terminal state can transition to any other. **Fix when**: integrating Pipecat pipeline (which will enforce its own transition logic).

### Production Readiness Score

**93/100** — Ready for current milestone. See full breakdown in audit artifact.

---

## Milestone 3 — Conversation State Machine

**Date**: 2026-07-02  
**Status**: ✅ Complete  
**Scope**: `app/conversation/` — Fine-grained FSM controlling voice conversation flow

### What Was Built

| File | Purpose |
|---|---|
| `exceptions.py` | `ConversationError` hierarchy: `InvalidTransitionError`, `TerminalStateError`, `InvalidStateError` |
| `transitions.py` | `ConversationState` enum (10 states) + immutable `TRANSITION_MAP` — single source of truth for all legal edges |
| `validators.py` | Pure functions `validate_transition()` (raises) and `can_transition()` (bool) |
| `events.py` | 10 frozen event dataclasses + `TransitionRecord` for audit history |
| `state_machine.py` | `ConversationStateMachine` — thread-safe FSM with strict validation, ordered history, reset/close convenience |
| `__init__.py` | Package API re-exports |

### Key Design Decisions

1. **Separate `ConversationState` (10 states) from `SessionState` (6 states)** — The conversation FSM models each pipeline stage individually (TRANSCRIBING, GENERATING_RESPONSE, GENERATING_AUDIO) while the session layer tracks coarse lifecycle. They coexist; the future pipeline coordinator synchronises both.

2. **Immutable `TRANSITION_MAP` (frozenset values)** — The map is a module-level constant. All validation delegates to it. No ad-hoc transition checks scattered across code.

3. **Raising exceptions for invalid transitions** — Unlike `SessionManager.set_state()` which returns `bool`, the FSM raises `InvalidTransitionError` / `TerminalStateError`. The caller must handle explicitly — fail-fast for pipeline correctness.

4. **Pure validator functions** — `validators.py` contains stateless functions. State machine delegates validation there, keeping its own code focused on mutation + history.

5. **Event models only (no bus)** — 10 frozen event dataclasses are defined for the future Event Bus milestone. No dispatch logic yet.

6. **One FSM per session** — Each `ConversationStateMachine` is bound to a `session_id` at construction. Loose coupling — no import of `SessionManager`.

7. **`TransitionRecord` audit log** — Append-only list of immutable records with from_state, to_state, timestamp, reason, session_id. Enables latency analysis and debugging.

### Transition Diagram

```
IDLE → LISTENING → TRANSCRIBING → THINKING → GENERATING_RESPONSE → GENERATING_AUDIO → SPEAKING → LISTENING (loop)
                                                                                           ↓
                                                                                      INTERRUPTED → LISTENING
Any active state → ERROR → IDLE (recovery) or CLOSED
Any non-terminal state → CLOSED (terminal)
```

### Test Suite

| File | Tests | Category |
|---|---|---|
| `test_conversation_transitions.py` | 39 | Enum, map completeness, all valid/invalid edges, validators |
| `test_conversation_events.py` | 25 | All 10 event types + TransitionRecord construction/serialization |
| `test_conversation_state_machine.py` | 38 | Init, transitions, flows, set_state, can_transition, reset, close, serialization |
| `test_conversation_edge_cases.py` | 34 | Exception hierarchy, self-transitions, multi-close, ERROR/INTERRUPTED constraints |
| `test_conversation_thread_safety.py` | 4 | Concurrent transitions, close race, concurrent reads, 100 independent FSMs |

### Quality Metrics (Full Project)

| Metric | Result |
|---|---|
| Total tests | 312/312 passed (1.83s) |
| Line coverage | 100% (330 statements) |
| Branch coverage | 100% (26 branches) |
| Ruff | Clean |
| Mypy (strict) | Clean |

### Integration Notes

- `app/session/` was **not modified** — the conversation package is additive.
- The future **Pipeline Coordinator** will hold both a `SessionManager` and a `Dict[str, ConversationStateMachine]`, synchronising session state with conversation state.
- The milestone 2 finding ("no state transition validation matrix" in SessionManager) is now **resolved** by this dedicated FSM layer.

---

## Milestone 4 — Event Bus

**Date**: 2026-07-02  
**Status**: ✅ Complete  
**Scope**: `app/events/` — Asynchronous publish-subscribe messaging backbone

### What Was Built

| File | Purpose |
|---|---|
| `event_types.py` | 20 strongly typed, frozen dataclass events spanning Session, Conversation, Pipeline, Error, and Metrics domains |
| `subscriber.py` | `Subscriber` model with exact/wildcard pattern matching, priority ordering, and one-shot delivery flags |
| `registry.py` | Thread-safe / async-safe registry for managing subscriptions |
| `dispatcher.py` | Strict sequential dispatcher isolating handler failures so one bad subscriber doesn't kill the bus |
| `middleware.py` | Async chain-of-responsibility middleware pipeline (includes `LoggingMiddleware` and `MetricsMiddleware`) |
| `publisher.py` | Segregated `Publisher` protocol for components that only emit events |
| `bus.py` | `EventBus` orchestrating the above, handling sync-to-async boundary crossing via a background worker task |
| `exceptions.py` | `EventBusError` hierarchy |

### Key Design Decisions

1. **Framework-agnostic handlers** — Handlers are plain async callables `async def fn(event: Event) -> None`. No base classes or decorators required, drastically lowering the barrier to entry.
2. **Interface Segregation** — Exposing a pure `Publisher` protocol so downstream components don't need to know about the `EventBus` internals or subscriber registry.
3. **Async / Sync bridging** — The `EventBus` manages a background `asyncio.Task` queue, exposing `publish_sync(event)` for blocking endpoints (like FastAPI sync routes) to fire-and-forget events into the async ecosystem.
4. **Resilient Dispatch** — If 5 subscribers match an event and the 2nd one raises an exception, the dispatcher catches it, logs it, executes the remaining 3, and only *then* raises a `HandlerExecutionError` wrapping the first failure.
5. **Wildcard Routing** — Subscribers can listen to `"Pipeline*"` or `"ConversationStarted"` using standard glob matching.

### Architecture Flow

```text
Publisher (STT / API / Pipeline)
  ↓ publish(event)
EventBus (Middleware Chain)
  ↓ routes via Registry
Dispatcher
  ↓ executes in priority order
Subscribers (1..N async callables)
```

### Test Suite

| File | Tests | Category |
|---|---|---|
| `test_event_registry.py` | 9 | Registration, unregistration, wildcard matching, priority sorting, one-shot cleanup |
| `test_event_dispatcher.py` | 5 | Success, one-shot IDs, sync fallback, error isolation |
| `test_event_middleware.py` | 4 | Logging, metrics success/failure, chain short-circuiting |
| `test_event_bus.py` | 5 | No-subscribers, batch publishing, sync background worker, middleware execution/errors |
| `test_event_concurrency.py` | 3 | 100 concurrent subs, 100 concurrent publishers, high-volume fire-and-forget sync |
| `test_event_performance.py` | 3 | 1000 events throughput, 1x100 fanout latency, stable memory profile over 5K cycles |

---

## Milestone 5 — Pipeline Builder

**Date**: 2026-07-03  
**Status**: ✅ Complete  
**Scope**: `app/pipeline/` — Graph-based, framework-independent pipeline builder

### What Was Built

| File | Purpose |
|---|---|
| `processors.py` | `ProcessorNode` frozen dataclass and `ProcessorRole` enum representing execution stages |
| `models.py` | Immutable `Pipeline` dataclass containing the built graph and processor definitions |
| `graph.py` | `PipelineGraph` internal mutable DAG manager with O(V+E) DFS cycle detection |
| `validators.py` | Topology validation (detects empty graphs, missing roots, multiple inputs, disconnected networks) |
| `builder.py` | Fluent `PipelineBuilder` supporting insertions, replacements, and emitting lifecycle events to the Event Bus |
| `factory.py` | `PipelineFactory` offering pre-built templates (Voice Pipeline, Text Pipeline) |
| `serializer.py` | `PipelineSerializer` enabling round-trip JSON serialization/deserialization |
| `exceptions.py` | Custom exception hierarchy (`InvalidPipelineError`, `CircularDependencyError`, etc.) |

### Key Design Decisions

1. **Strict Immutability Boundary** — The builder mutates internal state (`_processors`, `_graph`) guarded by a `threading.Lock`. Once `build()` is called, it emits a strictly immutable `Pipeline` dataclass.
2. **Abstract Topology over Execution** — The pipeline builder creates a purely descriptive DAG. It does NOT depend on Pipecat or execution semantics, allowing a future `PipelineRunner` to adapt the DAG to whatever execution framework is required.
3. **Event Bus Integration** — The builder emits `PipelineCreated`, `ProcessorAdded`, `ProcessorRemoved`, `PipelineValidated`, `PipelineBuildSucceeded`, and `PipelineBuildFailed` directly to the `EventBus` implemented in Milestone 4.
4. **Pre-Validation Guarantees** — Cycle detection runs *during* graph mutation (`add_edge`), preventing the graph from ever entering an invalid cyclic state. Final topological requirements (like single root validation) run on `build()`.

### Architecture Flow

```text
PipelineBuilder
  ↓ add_processor(), connect(), insert_before()
PipelineGraph (DFS Cycle Detection)
  ↓ validate()
Validators (Topology Rules)
  ↓ build()
Pipeline (Immutable Data Object)
```

### Test Suite

| File | Tests | Category |
|---|---|---|
| `test_pipeline_builder.py` | 8 | Builder API (add, remove, replace, insert_before/after, build failures) |
| `test_pipeline_validators.py` | 4 | Topology rules (empty, no-edges, multiple inputs, multiple roots) |
| `test_pipeline_graph.py` | 5 | DAG manipulation, orphaned edge cleanup, and DFS cycle detection |
| `test_pipeline_models.py` | 2 | Immutability, cloning, and processor dictionary formatting |
| `test_pipeline_factory.py` | 2 | Template structure generation (Voice & Text) |
| `test_pipeline_serializer.py`| 1 | Full JSON round-trip |

---

## Milestone 6 — Pipeline Runner

**Date**: 2026-07-03  
**Status**: ✅ Complete  
**Scope**: `app/pipeline/` (Runner) — Execution engine for immutable DAGs

### What Was Built

| File | Purpose |
|---|---|
| `runner.py` | `PipelineRunner` entry point wrapping scheduling, lifecycle, and execution |
| `executor.py` | `AbstractProcessor` interface and `DefaultProcessorExecutor` handles individual processor lifecycle & telemetry |
| `scheduler.py` | `PipelineScheduler` determining topological execution order using Kahn's algorithm |
| `lifecycle.py` | `PipelineLifecycleManager` and state machine (`INITIALIZED` → `RUNNING` → `COMPLETED`/`FAILED`) |
| `execution_state.py` | Explicit `ExecutionState` enumeration |
| `context.py` | Immutable `ExecutionContext` providing `execution_id`, metrics, and cancellation tokens |
| `cancellation.py` | Thread-safe `CancellationToken` for cooperative cancellation between stages |
| `metrics.py` | `MetricsCollector` tracking execution durations and component success rates |
| `queue.py` | `ExecutionQueue` wrapper around `asyncio.Queue` for inter-process buffer bridging |

### Key Design Decisions

1. **Topological Execution** — Extracted execution ordering into a dedicated `PipelineScheduler` which interprets the DAG created by `PipelineBuilder` into a valid sequential execution flow.
2. **Context Passing** — The execution engine injects a localized `ExecutionContext` into every processor, granting access to the `CancellationToken` and `MetricsCollector` without global state.
3. **Cooperative Cancellation** — Processors receive a `CancellationToken` and are expected to yield if cancelled. The runner enforces this by checking cancellation state *between* processor executions and short-circuiting.
4. **Rich Event Telemetry** — The runner broadcasts `PipelineInitialized`, `PipelineStarted`, `PipelinePaused`, `PipelineCancelled`, `ProcessorExecutionStarted`, etc. onto the existing Event Bus for full observability.
5. **Decoupled Execution** — The runner depends ONLY on `AbstractProcessor`. Implementations (like STT, LLM) are injected at runtime.

### Architecture Flow

```text
PipelineRunner (Start)
  ↓
PipelineScheduler (Sorts DAG)
  ↓
Loop Execution Order:
  → Executor.run(Processor, Context)
      ↓
    before_execute()
    execute()
    after_execute()
  ↓
PipelineRunner (Complete)
```

### Test Suite

| File | Tests | Category |
|---|---|---|
| `test_pipeline_runner.py` | 4 | Integration (Happy path, Missing implementations, Interruption, Pause/Resume) |
| `test_runner_scheduler.py`| 2 | Topological sorting algorithms |
| `test_runner_executor.py` | 3 | Processor execution wrapping and error bubbling |
| `test_runner_lifecycle.py`| 6 | State machine transition bounds and idempotency |
| `test_runner_metrics.py`  | 1 | Thread-safe telemetry collection |
| `test_runner_cancellation.py`| 1 | Cancellation token toggling |
| `test_runner_queue.py`    | 1 | Asyncio queue wrapper |

---

<!-- 
TEMPLATE FOR FUTURE ENTRIES — copy and fill in below this line:

## Milestone N — [Title]

**Date**: YYYY-MM-DD  
**Status**: 🔧 In Progress | ✅ Complete  
**Scope**: [files/modules affected]

### What Was Built
[description]

### Key Design Decisions
[numbered list]

### Issues / Trade-offs
[what was discovered, what was deferred]

-->
