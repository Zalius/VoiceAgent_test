"""
نسخه‌ی نهایی عامل صوتی مصاحبه شرکت OnTime - به‌روزرسانی کامل رفتار منطقی
=========================================================================
زیرساخت: LiveKit + OpenAI STT (fa) + Silero VAD + OpenAI TTS (sage) + GPT‑4.1-mini  
روند مصاحبه: خوش‌آمد → اطلاعات شخصی → تحصیلات → تجربه کاری → سوالات HR → سوالات فنی (با اصرار و skip کنترل‌شده) → جمع‌بندی → ذخیره پس از پایان تماس
"""

from dotenv import load_dotenv
import os, json
from datetime import datetime
from livekit import agents
from livekit.agents import Agent
from livekit.plugins import openai, silero

load_dotenv(".env")


class OnTimeInterviewAgentFA(Agent):
    """مصاحبه‌گر فارسی شرکت OnTime با رفتار انسانی و پله‌پله، بدون پرش مرحله‌ای."""

    def __init__(self):
        super().__init__(
            instructions=(
                "تو مصاحبه‌گر رسمی شرکت OnTime هستی. کاملاً محترمانه و رسمی صحبت کن. "
                "هر سؤال را جداگانه بپرس و منتظر پاسخ بمان، بعد به مرحله بعد برو. "
                "در سوالات فنی اگر پاسخ ناقص بود، دو بار به‌آرامی از کاربر بخواه که توضیح بیشتری بدهد. "
                "اگر باز هم نخواست یا گفت 'رد کن' یا 'نمی‌دانم'، فقط همان سؤال را رد کن، نه کل بخش فنی."
            )
        )
        self.state = "GREETING"
        self.candidate = {
            "name": None,
            "personal": {},
            "education": None,
            "experience": None,
            "hr_answers": [],
            "technical_answers": []
        }

        self.hr_questions = [
            "چرا دوست دارید در شرکت ما کار کنید؟",
            "آینده شغلی خودتون رو چطور می‌بینید؟",
            "در محیط کاری چه چیزهایی برای شما مهمه؟"
        ]
        self.tech_questions = [
            "تفاوت شبکه‌های RNN و LSTM چیه؟",
            "چرا شبکه‌های CNN در تشخیص تصویر مؤثر هستند؟",
            "در پروژه‌های یادگیری ماشین، نرمال‌سازی داده‌ها چه اهمیتی دارد؟",
            "فرق بین یادگیری نظارت‌شده و بدون‌نظارت چیه؟"
        ]
        self.hr_index = 0
        self.tech_index = 0
        self.insist_count = 0


    async def summarize_text(self, ctx):
        data = json.dumps(self.candidate, ensure_ascii=False)
        prompt = "خلاصه‌ی رسمی از محتوای مصاحبه صوتی زیر بنویس:\n" + data
        result = await ctx.session.llm.respond(prompt)
        return result.text.strip()


    # 🟢 شروع مصاحبه
    async def on_start(self, ctx):
        greeting = (
            "سلام 🌸 خوش‌آمدید به مصاحبه‌ی شرکت آن‌تایم. "
            "برای شروع، لطفاً نام کامل خودتون رو بفرمایید."
        )
        print("🗣 شروع:", greeting)
        await ctx.session.say(greeting, rate=0.9)
        self.state = "ASK_NAME"
        ctx.session.on_event("call_ended", lambda *_: self.on_call_end(ctx))


    # 🎧 واکنش به گفتار کاربر در هر مرحله
    async def on_user_spoke(self, ctx, text: str):
        text = text.strip()
        if not text:
            return

        # 🧩 نام
        if self.state == "ASK_NAME":
            self.candidate["name"] = text
            await ctx.session.say("خیلی ممنون، حالا لطفاً سنتون و محل زندگی‌تون رو بفرمایید.", rate=0.9)
            self.state = "ASK_PERSONAL"
            return

        # 🧩 اطلاعات شخصی
        elif self.state == "ASK_PERSONAL":
            self.candidate["personal"]["details"] = text
            await ctx.session.say("عالی! لطفاً درباره‌ی تحصیلاتتون کمی توضیح بدید.", rate=0.9)
            self.state = "ASK_EDUCATION"
            return

        # 🧩 تحصیلات
        elif self.state == "ASK_EDUCATION":
            self.candidate["education"] = text
            await ctx.session.say(
                "خیلی خوب، حالا می‌خوام بیشتر درباره‌ی تجربه کاری شما بدونم. کجاها کار کردید و روی چه پروژه‌هایی بودید؟",
                rate=0.9
            )
            self.state = "ASK_EXPERIENCE"
            return

        # 🧩 تجربه کاری
        elif self.state == "ASK_EXPERIENCE":
            self.candidate["experience"] = text
            await ctx.session.say("سپاس، حالا چند سؤال منابع انسانی ازتون می‌پرسم.", rate=0.85)
            await ctx.session.say(self.hr_questions[self.hr_index], rate=0.9)
            self.state = "HR_STAGE"
            return

        # 🧩 HR
        elif self.state == "HR_STAGE":
            # رد یا پاسخ دادن
            if "رد" in text or "skip" in text.lower() or "نمی" in text:
                await ctx.session.say("باشه، می‌ریم سر سؤال بعدی.", rate=0.9)
            else:
                self.candidate["hr_answers"].append(text)
                await ctx.session.say("خیلی خوب، ممنون از پاسخ‌تون.", rate=0.9)

            self.hr_index += 1
            if self.hr_index < len(self.hr_questions):
                await ctx.session.say(self.hr_questions[self.hr_index], rate=0.9)
            else:
                # بعد از HR، صرف‌نظر از پاسخ‌ها، همیشه برو به بخش فنی
                await ctx.session.say("بسیار عالی، حالا وارد بخش فنی مصاحبه می‌شویم.", rate=0.9)
                await ctx.session.say(self.tech_questions[self.tech_index], rate=0.9)
                self.state = "TECH_STAGE"
            return

        # 🧩 TECH
        elif self.state == "TECH_STAGE":
            skip_trigger = any(p in text for p in ["رد", "skip", "نمی", "نمیدونم"])
            short_answer = len(text.split()) < 3

            if skip_trigger:
                # اگر کاربر گفت رد یا نمی‌دانم، اما هنوز دو بار اصرار نکرده
                if self.insist_count < 2:
                    self.insist_count += 1
                    msg = (
                        "فهمیدم، اما لطفاً حداقل یک توضیح کوتاه درباره‌ی اینکه آیا با این موضوع آشنا هستید یا نه بدید."
                        if self.insist_count == 1 else
                        "اگر نمی‌خواید پاسخ بدید، فقط بفرمایید تا به سؤال بعدی بریم."
                    )
                    await ctx.session.say(msg, rate=0.9)
                    return
                else:
                    await ctx.session.say("باشه، می‌ریم سر سؤال بعدی.", rate=0.9)
                    self.insist_count = 0
                    self.tech_index += 1

            elif short_answer:
                # پاسخ خیلی کوتاه، اصرار ملایم برای شرح بیشتر
                if self.insist_count < 2:
                    self.insist_count += 1
                    await ctx.session.say("ممکنه لطفاً کمی بیشتر توضیح بدید یا مثالی بزنید؟", rate=0.9)
                    return
                else:
                    self.candidate["technical_answers"].append(text)
                    self.insist_count = 0
                    self.tech_index += 1
            else:
                # پاسخ کامل
                self.candidate["technical_answers"].append(text)
                await ctx.session.say("سپاس از توضیح‌تون.", rate=0.9)
                self.insist_count = 0
                self.tech_index += 1

            # مرحله بعدی یا اتمام
            if self.tech_index < len(self.tech_questions):
                await ctx.session.say(self.tech_questions[self.tech_index], rate=0.9)
            else:
                await ctx.session.say("خیلی خوب، بخش فنی تموم شد. ممنون از همکاری شما.", rate=0.9)
                await ctx.session.say("ما بررسی می‌کنیم و نتیجه مصاحبه رو به‌زودی اعلام می‌کنیم.", rate=0.9)
                await ctx.session.say("مصاحبه به پایان رسیده، می‌تونید تماس رو قطع کنید.", rate=0.9)
                self.state = "WAIT_END"
            return


    # 🟠 پایان تماس و ذخیره خروجی
    async def on_call_end(self, ctx):
        print("📞 تماس پایان یافت. ذخیره فایل خلاصه...")
        summary_text = await self.summarize_text(ctx)
        data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "candidate_name": self.candidate["name"],
            "personal": self.candidate["personal"],
            "education": self.candidate["education"],
            "experience": self.candidate["experience"],
            "hr_answers": self.candidate["hr_answers"],
            "technical_answers": self.candidate["technical_answers"],
            "summary": summary_text
        }
        with open("ontime_interview_session_fa.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print("✅ فایل خلاصه ذخیره شد: ontime_interview_session_fa.json")


# ======================================================
async def entrypoint(ctx: agents.JobContext):
    """راه‌انداز عامل مصاحبه OnTime"""
    session = agents.AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe", language="fa"),
        llm=openai.LLM(model=os.getenv("LLM_CHOICE", "gpt-4.1-mini")),
        tts=openai.TTS(voice="sage"),
        vad=silero.VAD.load(),
    )
    await session.start(room=ctx.room, agent=OnTimeInterviewAgentFA())


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
