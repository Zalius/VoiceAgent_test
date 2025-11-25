"""
نسخه فارسی عامل مصاحبه صوتی شرکت OnTime با استفاده از Avasho TTS
---------------------------------------------------------------
"""

from dotenv import load_dotenv
import os
import json
import requests
from datetime import datetime
import tempfile
from types import SimpleNamespace
import aiofiles

from livekit import agents
from livekit.agents import Agent
from livekit.plugins import silero, openai
from livekit.agents.tts import ChunkedStream


# ---------------------- ENV ----------------------
load_dotenv(".env")
AVASHO_TOKEN = os.getenv("AVASHO_GATEWAY_TOKEN")


# ======================================================
# کلاس کوچک Avasho TTS جایگزین openai.TTS
# ======================================================
class AvashoTTS:
    API_URL = "https://partai.gw.isahab.ir/avasho/v2/avasho/request"

    def __init__(self, speaker="shahrzad", speed=1.0, timestamp=True):
        self.speaker = speaker
        self.speed = speed
        self.timestamp = timestamp
        self.token = os.getenv("AVASHO_GATEWAY_TOKEN")
        self.format = "mp3"
        self.sample_rate = 24000
        self.num_channels = 1
        self.capabilities = SimpleNamespace(streaming=False, format=self.format)
        self._event_handlers = {}

    def on(self, event_name: str):
        def decorator(handler_func):
            self._event_handlers.setdefault(event_name, []).append(handler_func)
            return handler_func
        return decorator

    def emit(self, event_name: str, *args, **kwargs):
        for handler in self._event_handlers.get(event_name, []):
            try:
                handler(*args, **kwargs)
            except Exception:
                pass

    def synthesize(self, text: str, rate: float = 1.0, **kwargs):
        headers = {
            "gateway-token": self.token,
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "speaker": self.speaker,
            "speed": self.speed,
            "timestamp": self.timestamp,
        }
        outer = self

        class SynthContext:
            def __init__(self):
                self._tmp_file = None

            async def __aenter__(self):
                try:
                    resp = requests.post(
                        outer.API_URL, headers=headers, data=json.dumps(payload)
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    audio_url = (
                        data.get("data", {})
                            .get("data", {})
                            .get("aiResponse", {})
                            .get("result", {})
                            .get("filename")
                    )
                    if not audio_url:
                        print("⚠️ Avasho response missing filename URL:", data)
                        return self

                    audio_data = requests.get(audio_url)
                    audio_data.raise_for_status()
                    self._tmp_file = tempfile.NamedTemporaryFile(
                        delete=False, suffix=".mp3"
                    )
                    async with aiofiles.open(self._tmp_file.name, "wb") as f:
                        await f.write(audio_data.content)

                    outer.emit("metrics_collected", {"bytes": len(audio_data.content)})
                    return self  # LiveKit uses `async for` on this context
                except Exception as e:
                    print("🚫 AvashoTTS synthesis failed:", e)
                    return self  # still return self so `async for` finds empty iterator

            async def __aexit__(self, exc_type, exc, tb):
                pass

            def __aiter__(self):
                return self._aiter()

            async def _aiter(self):
                if not self._tmp_file:
                    return
                async with aiofiles.open(self._tmp_file.name, "rb") as f:
                    audio_bytes = await f.read()
                    yield ChunkedStream.Chunk(
                        audio=audio_bytes,
                        sample_rate=outer.sample_rate,
                        num_channels=outer.num_channels,
                        format=outer.format,
                    )

        return SynthContext()


# ======================================================
# کلاس اصلی عامل مصاحبه (بدون تغییر در منطق)
# ======================================================
class OnTimeInterviewAgentFA(Agent):
    """مصاحبه‌گر حرفه‌ای شرکت OnTime به زبان فارسی (گویش رسمی و آرام)."""

    def __init__(self):
        super().__init__(
            instructions=(
                "شما مصاحبه‌گر منابع انسانی شرکت OnTime هستید. "
                "مصاحبه را کاملاً به زبان فارسی، با لحن جدی و محترمانه انجام دهید. "
                "ابتدا درباره‌ی تحصیلات بپرسید، سپس تجربه کاری، "
                "در ادامه پرسش‌های فنی در زمینه علم داده بپرسید و در پایان مودبانه خداحافظی کنید."
            )
        )

        self.state = "GREETING"
        self.resume = {
            "name": "Pooyan Alavi",
            "education": "Master of Science in Computer Science from Amirkabir University of Technology (2022)",
            "experience": [
                "Data Scientist at DataMind Solutions (2022–2024)",
                "Front-End Developer at TechBridge Studio (2020–2021)"
            ],
            "skills": ["Python", "TensorFlow", "React", "TypeScript", "SQL", "Docker", "Kubernetes"],
        }
        self.candidate = {"name": self.resume["name"], "education": None, "experience": None, "technical": None}

    # ---------------- خلاصه‌سازی ----------------
    async def summarize_answer(self, ctx, full_text: str, section: str):
        if not full_text:
            return None
        prompt = (
            f"پاسخ زیر مربوط به بخش «{section}» مصاحبه است. آن را در دو جمله‌ی رسمی خلاصه کن:\n\n{full_text}"
        )
        result = await ctx.session.llm.respond(prompt)
        return result.text.strip()

    # ---------------- رویداد شروع ----------------
    async def on_start(self, ctx):
        greeting = (
            f"سلام {self.resume['name']} عزیز، خوش‌آمدید به مصاحبه‌ی شرکت آن‌تایم. "
            f"من رزومه‌ی شما را دیدم که در آن {self.resume['education']} نوشته شده است. "
            "لطفاً کمی درباره‌ی رشته و تمرکز تحصیلی‌تان توضیح دهید."
        )
        print(f"🗣 عامل می‌گوید: {greeting}")
        await ctx.session.say(greeting, rate=0.9)
        self.state = "EDUCATION"

    async def on_user_spoke(self, ctx, text: str):
        text = text.strip()
        if not text:
            return

        if self.state == "EDUCATION":
            self.candidate["education"] = text
            follow_up = (
                "خیلی عالی. حالا درباره‌ی مسیر حرفه‌ای‌تان صحبت کنیم. "
                f"طبق رزومه می‌دانم در این مجموعه‌ها فعالیت داشته‌اید: {', '.join(self.resume['experience'])}. "
                "می‌توانید درباره‌ی مسئولیت‌ها و فناوری‌هایی که استفاده می‌کردید توضیح دهید؟"
            )
            print(f"🗣 عامل می‌گوید: {follow_up}")
            await ctx.session.say(follow_up, rate=0.9)
            self.state = "EXPERIENCE"

        elif self.state == "EXPERIENCE":
            self.candidate["experience"] = text
            tech_q = (
                "خیلی ممنون از توضیحاتتان. "
                "اکنون می‌رسیم به بخش فنی. "
                "لطفاً توضیح دهید تفاوت شبکه‌های بازگشتی RNN با LSTM چیست "
                "و چرا شبکه‌های CNN برای تشخیص تصویر کارآمد هستند؟"
            )
            print(f"🗣 عامل می‌گوید: {tech_q}")
            await ctx.session.say(tech_q, rate=0.9)
            self.state = "TECH"

        elif self.state == "TECH":
            self.candidate["technical"] = text
            closing = (
                "سپاس از پاسخ‌ها و مشارکت شما در مصاحبه. "
                "مصاحبه در اینجا به پایان می‌رسد و در صورت نیاز با شما تماس خواهیم گرفت. روز خوبی داشته باشید!"
            )
            print(f"🗣 عامل می‌گوید: {closing}")
            await ctx.session.say(closing, rate=0.9)
            await self.save_summary(ctx)
            self.state = "CLOSE"

    async def save_summary(self, ctx):
        summary = {
            "candidate": self.candidate["name"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "education_full": self.candidate["education"],
            "education_brief": await self.summarize_answer(ctx, self.candidate["education"], "تحصیلات"),
            "experience_full": self.candidate["experience"],
            "experience_brief": await self.summarize_answer(ctx, self.candidate["experience"], "تجربه کاری"),
            "technical_full": self.candidate["technical"],
            "technical_brief": await self.summarize_answer(ctx, self.candidate["technical"], "فنی"),
        }

        with open("pooyan_alavi_interview_summary_fa.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=4, ensure_ascii=False)
        print("✅ خلاصه‌ی مصاحبه در فایل pooyan_alavi_interview_summary_fa.json ذخیره شد.")


# ======================================================
# ENTRYPOINT
# ======================================================
async def entrypoint(ctx: agents.JobContext):
    session = agents.AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe", language="fa"),
        llm=openai.LLM(model=os.getenv("LLM_CHOICE", "gpt-4.1-mini")),
        tts=AvashoTTS(speaker="shahrzad", speed=1.0),  # 🟢 جایگزین TTS آواشو
        vad=silero.VAD.load(),
    )
    await session.start(room=ctx.room, agent=OnTimeInterviewAgentFA())


# ======================================================
# اجرای عامل
# ======================================================
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
