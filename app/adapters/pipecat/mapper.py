"""
Mapper to convert internal Pipeline to Pipecat processors.
"""

from typing import List

from loguru import logger

from app.pipeline.models import Pipeline
from app.pipeline.scheduler import PipelineScheduler
from .exceptions import PipelineConversionError, ProcessorMappingError
from .processors import PipecatProcessorAdapter, create_pipecat_processor


class PipecatPipelineMapper:
    """Converts our internal Pipeline into a sequence of Pipecat processors."""
    
    @staticmethod
    def map_pipeline(pipeline: Pipeline, transport_type: str = "livekit") -> List[PipecatProcessorAdapter]:
        """Convert a DAG pipeline to a linear pipecat sequence.
        
        Pipecat pipelines are typically linear arrays:
        [TransportInput, STT, LLM, TTS, TransportOutput]
        
        We use the PipelineScheduler to get the topological order.
        """
        logger.debug(f"Converting pipeline {pipeline.pipeline_id} to Pipecat format with transport_type={transport_type}")
        
        try:
            scheduler = PipelineScheduler(pipeline)
            order = scheduler.get_execution_order()
            
            pipecat_processors = []
            
            for processor_id in order:
                node = pipeline.processors.get(processor_id)
                if not node:
                    raise ProcessorMappingError(f"Processor {processor_id} not found in pipeline")
                    
                # Create the actual pipecat instance
                raw_processor = create_pipecat_processor(node.role, node.metadata, transport_type=transport_type)
                adapter = PipecatProcessorAdapter(node.processor_id, raw_processor)
                pipecat_processors.append(adapter)
                
            return pipecat_processors
            
        except Exception as e:
            raise PipelineConversionError(f"Failed to convert pipeline: {e}") from e
