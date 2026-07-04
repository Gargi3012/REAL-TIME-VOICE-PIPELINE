import pytest
from unittest.mock import patch, MagicMock
from app.pipeline.processors import ProcessorRole
from app.adapters.pipecat.processors import (
    PipecatProcessorAdapter,
    MockPipecatProcessor,
    create_pipecat_processor,
    _create_mock_processor
)


def test_pipecat_processor_adapter():
    mock_inner = MagicMock()
    adapter = PipecatProcessorAdapter("test_processor", mock_inner)
    assert adapter.name == "test_processor"
    assert adapter.get_processor() is mock_inner


def test_create_mock_processor():
    mock_stt = _create_mock_processor(ProcessorRole.STT)
    assert mock_stt.name == "MockSTT"
    assert isinstance(mock_stt, MockPipecatProcessor)

    mock_llm = _create_mock_processor(ProcessorRole.LLM)
    assert mock_llm.name == "MockLLM"


@patch("app.adapters.pipecat.processors._create_real_processor")
def test_create_pipecat_processor_success(mock_create_real):
    """Test factory when pipecat-ai is installed (mocked)."""
    mock_real = MagicMock()
    mock_create_real.return_value = mock_real

    result = create_pipecat_processor(ProcessorRole.STT, {})
    assert result is mock_real
    mock_create_real.assert_called_once_with(ProcessorRole.STT, {})


@patch("app.adapters.pipecat.processors._create_real_processor", side_effect=ImportError("No pipecat"))
def test_create_pipecat_processor_fallback(mock_create_real):
    """Test factory fallback to mock when pipecat-ai is missing."""
    result = create_pipecat_processor(ProcessorRole.STT, {})
    assert isinstance(result, MockPipecatProcessor)
    assert result.name == "MockSTT"
    mock_create_real.assert_called_once_with(ProcessorRole.STT, {})


@patch("app.config.DEEPGRAM_API_KEY", "test_key")
def test_create_real_processor_stt_missing_pipecat():
    """Test real STT processor creation raises ImportError in CI where pipecat is missing."""
    with pytest.raises(ImportError):
        # We don't mock the imports inside _create_real_processor here,
        # so it should raise ImportError when it tries to import pipecat.services.deepgram.
        from app.adapters.pipecat.processors import _create_real_processor
        _create_real_processor(ProcessorRole.STT, {})
