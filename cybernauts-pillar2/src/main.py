
import asyncio
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor

from transport import get_daily_transport, register_transport_events
from deepgram_stt import get_deepgram_stt, wrap_stt_with_logging
from logger import log_event, log_error, reset_timer


class PrintTranscript(FrameProcessor):
    """
    Prints whatever text Deepgram produces, and logs the exact
    moment it happens (used to measure audio-in -> text-out latency).
    This is ONLY here to prove Pillar 2's job is working.
    Pillar 1 will replace this with the real pipeline that sends
    the text onward to the LLM.
    """

    async def process_frame(self, frame, direction):
        if isinstance(frame, TranscriptionFrame):
            log_event("TEXT_READY", extra=frame.text)
            print(f"[USER SAID]: {frame.text}")
            reset_timer()  # reset for the next conversation turn

        await self.push_frame(frame, direction)


async def main():
    try:
        # ---- THIS IS YOUR ENTIRE JOB (Pillar 2) ----
        log_event("PIPELINE_STARTING")

        transport = get_daily_transport()   # audio IN/OUT door (WebRTC)
        register_transport_events(transport)  # log join/leave/errors

        stt = get_deepgram_stt()            # audio -> text (Deepgram)
        stt = wrap_stt_with_logging(stt)    # log exactly when transcript arrives (latency tracking)
        printer = PrintTranscript()         # proof it works + logs timing

        pipeline = Pipeline(
            [
                transport.input(),  # 1. user's mic audio comes in
                stt,                # 2. audio converted to text
                printer,            # 3. text gets printed + logged
            ]
        )

        task = PipelineTask(pipeline)
        runner = PipelineRunner()

        print("Join your Daily room and speak. Your words will print below:")
        log_event("PIPELINE_READY", extra="waiting for user to join")

        await runner.run(task)

    except Exception as e:
        log_error("main() - Pillar 2 pipeline", e)
        print(f"\nSomething went wrong: {e}")
        print("Check the logs above for exactly where it failed.")
        raise

    finally:
        log_event("PIPELINE_STOPPED")


if __name__ == "__main__":
    asyncio.run(main())