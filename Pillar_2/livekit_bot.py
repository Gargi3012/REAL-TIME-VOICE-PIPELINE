def build_livekit_transport(room_url: str, token: str, room_name: str, vad_analyzer):
    """Exposed factory for the main app to build the LiveKit transport via Pillar 2."""
    from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport

    return LiveKitTransport(
        url=room_url,
        token=token,
        room_name=room_name,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_enabled=True,
            audio_out_sample_rate=16000,
            vad_enabled=True,
            vad_analyzer=vad_analyzer,
            audio_out_is_live=True,
        ),
    )