"""
نسخه فارسی عامل مصاحبه صوتی شرکت OnTime
========================================
مصاحبه‌گر صوتی بلادرنگ برای استخدام در شرکت OnTime
زیرساخت: OpenAI STT (fa) + Silero VAD + OpenAI TTS (alloy) + OpenAI LLM
جریان مصاحبه: سلام و معرفی → تحصیلات → تجربه کاری → سوالات فنی → پایان محترمانه
"""

from dotenv import load_dotenv
import os
import json
from datetime import datetime

from livekit import agents
from livekit.agents import Agent
from livekit.plugins import silero, openai


# ---------------------- ENV ----------------------
load_dotenv(".env")


# ======================================================
# کلاس اصلی عامل مصاحبه
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

        # رزومه‌ی انگلیسی خوانده شده از فایل JSON
        self.resume = {
            "name": "Pooyan Alavi",
            "education": "Master of Science in Computer Science from Amirkabir University of Technology (2022)",
            "experience": [
                "Data Scientist at DataMind Solutions (2022–2024)",
                "Front-End Developer at TechBridge Studio (2020–2021)"
            ],
            "skills": ["Python", "TensorFlow", "React", "TypeScript", "SQL", "Docker", "Kubernetes"],
        }

        self.candidate = {
            "name": self.resume["name"],
            "education": None,
            "experience": None,
            "technical": None,
        }

    # ---------------- خلاصه‌سازی ----------------
    async def summarize_answer(self, ctx, full_text: str, section: str):
        """خلاصه کوتاه و رسمی از پاسخ شرکت‌کننده بر اساس LLM."""
        if not full_text:
            return None
        prompt = (
            f"پاسخ زیر مربوط به بخش «{section}» مصاحبه است. آن را در دو جمله‌ی رسمی خلاصه کن:"
            f"\n\n{full_text}"
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

    # ---------------- هنگامی که کاربر صحبت کرد ----------------
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

    # ---------------- ذخیره نتایج ----------------
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

        print("✅ خلاصه‌ی مصاحبه (کامل + خلاصه) در فایل pooyan_alavi_interview_summary_fa.json ذخیره شد.")


# ======================================================
# ENTRYPOINT
# ======================================================
async def entrypoint(ctx: agents.JobContext):
    """راه‌اندازی کامل جلسه‌ی صوتی فارسی."""
    #alloy, echo, verse   female: coral, sage, marin , cedar   nova, onyx
    # onyx, marin, alloy, marin, sage
    session = agents.AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe", language="fa"),
        llm=openai.LLM(model=os.getenv("LLM_CHOICE", "gpt-4.1-mini")),
        tts=openai.TTS(voice="sage"),
        vad=silero.VAD.load(),
    )

    await session.start(room=ctx.room, agent=OnTimeInterviewAgentFA())


# ======================================================
# اجرای عامل
# ======================================================
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
