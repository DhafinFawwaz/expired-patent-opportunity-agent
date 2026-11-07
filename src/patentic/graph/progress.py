from langgraph.config import get_stream_writer


def emit(stage: str, event: str, **detail: object) -> None:
    writer = get_stream_writer()
    writer({"stage": stage, "event": event, **detail})
