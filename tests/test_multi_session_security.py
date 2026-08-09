"""
Tests for Multi-Session Security & Race Conditions.
Simulates 100 concurrent users performing random operations on the framework.
"""

import asyncio
import random
import pytest

from app.session.manager import SessionManager
from app.events.bus import EventBus
from app.events.event_types import PipelineStarted
from app.conversation.state_machine import ConversationStateMachine
from app.conversation.transitions import ConversationState
from app.pipeline.builder import PipelineBuilder
from app.pipeline.processors import ProcessorNode, ProcessorRole


@pytest.mark.asyncio
async def test_multi_session_race_conditions() -> None:
    """100 concurrent users doing random operations."""
    manager = SessionManager()
    bus = EventBus()
    
    async def simulate_user(idx: int) -> None:
        # Create
        session = await manager.create_session()
        sid = session.session_id
        
        # Add message
        await manager.add_message(sid, "user", f"msg {idx}")
        
        # Publish event
        evt = PipelineStarted(
            session_id=sid,
            payload={"msg": idx}
        )
        await bus.publish(evt)
        
        # State machine
        fsm = ConversationStateMachine(sid)
        fsm.transition_to(ConversationState.LISTENING)
        
        # Build Pipeline
        b = PipelineBuilder(bus, sid)
        b.add_processor(ProcessorNode(f"STT_{idx}", ProcessorRole.STT))
        b.build()
        
        # Random sleep to induce thread shifting
        await asyncio.sleep(random.uniform(0.001, 0.01))
        
        fsm.transition_to(ConversationState.CLOSED)
        await manager.delete_session(sid)
        
    tasks = [asyncio.create_task(simulate_user(i)) for i in range(100)]
    
    await asyncio.gather(*tasks)
    
    # Assert deterministic finish
    assert (await manager.total_sessions()) == 0
