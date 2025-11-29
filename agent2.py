import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)
from livekit.plugins import openai, silero
from livekit import rtc

logger = logging.getLogger("voice-agent")
logger.setLevel(logging.DEBUG)  # Changed to DEBUG


class VoiceAssistant(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are a helpful conversational voice assistant. "
                "You speak Persian (Farsi). "
                "Keep your responses short, friendly, and spoken in natural Persian."
            )
        )


async def entrypoint(ctx: JobContext):
    logger.info("⏳ Connecting to LiveKit room...")
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)

    logger.info(f"✅ Agent connected to room: {ctx.room.name}")

    # Debug: Listen for track subscriptions
    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication, participant):
        logger.info(f"🎵 Track subscribed: {track.kind} from {participant.identity}")

    @ctx.room.on("track_unsubscribed")
    def on_track_unsubscribed(track: rtc.Track, publication, participant):
        logger.info(f"❌ Track unsubscribed: {track.kind} from {participant.identity}")

    participant = await ctx.wait_for_participant()
    logger.info(f"🎤 Participant joined: {participant.identity}")

    # Log existing tracks
    for track_pub in participant.track_publications.values():
        logger.info(f"📡 Existing track: {track_pub.kind} - subscribed: {track_pub.subscribed}")

    session = AgentSession(
        stt=openai.STT(
            model="whisper-1",
            language="fa",
        ),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="alloy"),
        vad=silero.VAD.load(
            min_speech_duration=0.1,
            min_silence_duration=0.3,
        ),
    )

    # Debug: Listen for speech events
    @session.on("user_started_speaking")
    def on_user_speaking():
        logger.info("🗣️ USER STARTED SPEAKING!")

    @session.on("user_stopped_speaking")
    def on_user_stopped():
        logger.info("🤐 USER STOPPED SPEAKING")

    @session.on("agent_started_speaking")
    def on_agent_speaking():
        logger.info("🔊 AGENT STARTED SPEAKING")

    @session.on("agent_stopped_speaking")
    def on_agent_stopped():
        logger.info("🔇 AGENT STOPPED SPEAKING")

    await session.start(
        agent=VoiceAssistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            audio_enabled=True,
            video_enabled=False,
            text_enabled=True,
        ),
    )

    await session.say("سلام! چطور می‌تونم کمکتون کنم؟", allow_interruptions=True)

    await asyncio.Future()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
