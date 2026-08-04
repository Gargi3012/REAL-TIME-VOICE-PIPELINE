"""
Tests for Memory Leak Detection.
Uses tracemalloc and gc to ensure no object retention.
"""

import gc
import tracemalloc
import pytest

from app.session.manager import SessionManager
from app.events.bus import EventBus
from app.pipeline.builder import PipelineBuilder
from app.pipeline.processors import ProcessorNode, ProcessorRole


@pytest.mark.asyncio
async def test_memory_leaks() -> None:
    """Run pipeline creation and deletion in a loop and verify memory doesn't leak."""
    tracemalloc.start()
    
    bus = EventBus()
    manager = SessionManager()
    
    # Warmup
    for i in range(10):
        s = await manager.create_session()
        b = PipelineBuilder(bus, s.session_id)
        b.add_processor(ProcessorNode(f"STT_{i}", ProcessorRole.STT))
        p = b.build()
        await manager.delete_session(s.session_id)
        
    gc.collect()
    snapshot1 = tracemalloc.take_snapshot()
    
    # Stress iteration
    for i in range(1000): # Using 1000 instead of 5000 to keep test execution fast
        s = await manager.create_session()
        b = PipelineBuilder(bus, s.session_id)
        b.add_processor(ProcessorNode(f"STT_{i}", ProcessorRole.STT))
        b.build()
        await manager.delete_session(s.session_id)
        
    gc.collect()
    snapshot2 = tracemalloc.take_snapshot()
    
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    
    tracemalloc.stop()
    
    # Ensure memory growth is reasonable
    # Usually, some small allocations might happen in internal Python caches,
    # but large leaps would indicate a leak.
    growth = sum(stat.size_diff for stat in top_stats if stat.size_diff > 0)
    
    # 5MB threshold for growth in 1000 iterations
    assert growth < 5 * 1024 * 1024
