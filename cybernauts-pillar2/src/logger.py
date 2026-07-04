
import time
import logging

# Configure a clean, readable log format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("pillar2")

# Keeps track of the last event's timestamp so we can compute
# the time GAP between two events (useful for latency debugging)
_last_timestamp = None


def log_event(event_name: str, extra: str = ""):
    """
    Logs an event with a timestamp, and prints how much time
    passed since the last logged event (in milliseconds).
    """
    global _last_timestamp

    now = time.time()
    gap_ms = None
    if _last_timestamp is not None:
        gap_ms = round((now - _last_timestamp) * 1000, 2)

    _last_timestamp = now

    if gap_ms is not None:
        logger.info(f"{event_name} | +{gap_ms}ms since last event | {extra}")
    else:
        logger.info(f"{event_name} | {extra}")


def log_error(context: str, error: Exception):
    """
    Logs an error clearly, with context on WHERE it happened
    (e.g. 'Daily connection', 'Deepgram STT').
    """
    logger.error(f"ERROR in {context}: {type(error).__name__} - {error}")


def reset_timer():
    """Call this at the start of a new conversation turn to reset the gap timer."""
    global _last_timestamp
    _last_timestamp = None