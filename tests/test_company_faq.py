import pytest
from unittest.mock import patch, MagicMock
from app.llm.company_faq import get_faq_context_block, refresh_faq_cache

@pytest.mark.asyncio
async def test_refresh_faq_cache_success():
    # Mock FAQ repository data
    mock_faq = MagicMock()
    mock_faq.category = "About the Company"
    mock_faq.question = "What does Cybernauts do?"
    mock_faq.answer = "Cybernauts is an AI automation agency."

    with patch("app.repositories.faq_repository.FAQRepository.get_all") as mock_get_all:
        mock_get_all.return_value = [mock_faq]
        
        # Call refresh cache
        await refresh_faq_cache()
        
        block = get_faq_context_block()
        assert "COMPANY KNOWLEDGE BASE — Cybernauts" in block
        assert "## About the Company" in block
        assert "Q: What does Cybernauts do?" in block
        assert "A: Cybernauts is an AI automation agency." in block

def test_context_block_is_string():
    block = get_faq_context_block()
    assert isinstance(block, str)