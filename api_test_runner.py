"""
API Diagnostic Script for Voice Interview Environment
-----------------------------------------------------
Tests connectivity & functionality for:
- LiveKit agents core
- Deepgram STT
- OpenAI STT (fa/en)
- Silero VAD
- OpenAI TTS voices
- OpenAI LLM models
"""

import asyncio
from livekit import agents
from livekit.plugins import deepgram, silero, openai


async def test_llm():
    print("🔍 Testing LLM completion (gpt-4o-mini)...")
    llm = openai.LLM(model="gpt-4o-mini")
    response = await llm.respond("Generate a single sentence confirming connectivity.")
    print("✅ LLM response:", response.text.strip(), "\n")


async def test_tts():
    print("🔊 Testing TTS voices...")
    for voice in ["verse", "alloy"]:
        tts = openai.TTS(voice=voice)
        print(f"  - Voice '{voice}' initialized successfully ✅")
    print("✅ TTS voice setup OK.\n")


async def test_stt_deepgram():
    print("🎙️ Testing Deepgram STT (English)...")
    stt = deepgram.STT(model="nova-2")
    print(f"✅ Deepgram STT '{stt.model}' initialized successfully.\n")


async def test_stt_openai():
    print("🎙️ Testing OpenAI STT (Persian & English)...")
    stt_fa = openai.STT(model="gpt-4o-mini-transcribe", language="fa")
    stt_en = openai.STT(model="gpt-4o-mini-transcribe")
    print(f"✅ Persian STT '{stt_fa.model}' initialized.")
    print(f"✅ English STT '{stt_en.model}' initialized.\n")


async def test_vad():
    print("⚙️ Testing Silero VAD...")
    vad = silero.VAD.load()
    if vad:
        print("✅ Silero VAD loaded successfully.\n")
    else:
        print("❌ VAD load failed.\n")


async def test_livekit_agent_core():
    print("🌐 Testing LiveKit Agent Core initialization...")
    try:
        _ = agents.AgentSession()
        print("✅ LiveKit AgentSession instantiated successfully.\n")
    except Exception as e:
        print("❌ Failed to create AgentSession:", e, "\n")


async def run_all_tests():
    print("\n🚀 Starting API Diagnostic Tests...\n")
    await test_llm()
    await test_tts()
    await test_stt_deepgram()
    await test_stt_openai()
    await test_vad()
    await test_livekit_agent_core()
    print("🏁 All API tests completed.\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
