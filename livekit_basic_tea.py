"""
نسخه فارسی عامل صوتی برای چای‌خانه آنتایم
=========================================
عامل گفت‌وگوی صوتی برای مشاوره، انتخاب و ثبت سفارش انواع چای سیاه ایرانی:
قلم، بهاره، ساقه، کله مورچه‌ای، ممتاز، باروتی و شکسته.

زیرساخت: OpenAI STT (fa) + Silero VAD + OpenAI TTS (sage) + OpenAI LLM
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
# کلاس اصلی عامل چای‌خانه
# ======================================================
class TeaShopAgentFA(Agent):
    """عامل فروشنده‌ و مشاور چای‌خانه چلچله‌سار به زبان فارسی."""

    def __init__(self):
        super().__init__(
            instructions=(
                "شما فروشنده‌ی چای‌خانه چلچله‌سار هستید. "
                "صاحب چای‌خانه چلچله‌سار خانوم شَهنام تَفَکٌری است. " 
                "با مشتری به زبان فارسی و با لحن صمیمی و محترمانه صحبت کنید. "
                "اطلاعات دقیق درباره‌ی انواع چای سیاه ایرانی و قیمت‌های تقریبی بدهید. "
                "در صورت تمایل مشتری، سفارش را ثبت کنید و جمع‌بندی مودبانه داشته باشید."
            )
        )

        self.state = "GREETING"
        self.customer = {"name": None, "requests": [], "chosen_tea": None, "summary": None}

        # انواع چای و قیمت‌ها
        self.teas = {
            "قلم": {"grade": ["درجه یک", "درجه دو"], "price": [250_000, 180_000]},
            "بهاره": {"grade": ["ممتاز", "درجه یک"], "price": [350_000, 280_000]},
            "ساقه": {"grade": ["درجه دو"], "price": [150_000]},
            "کَله مورچه‌ای": {"grade": ["ممتاز"], "price": [400_000]},
            "باروتی": {"grade": ["درجه سه"], "price": [120_000]},
            "شکسته": {"grade": ["درجه یک", "درجه دو"], "price": [220_000, 170_000]},
        }

    # ---------------- خلاصه‌سازی ----------------
    async def summarize_text(self, ctx, text):
        if not text:
            return None
        prompt = f"خلاصه‌ای محترمانه از مکالمه فروش در چای‌خانه بنویس:\n{text}"
        result = await ctx.session.llm.respond(prompt)
        return result.text.strip()

    # ---------------- شروع گفت‌وگو ----------------
    async def on_start(self, ctx):
        greeting = (
            "سلام و عرض ادب! به چای‌خانه‌ی  چلچله‌سار خوش‌آمدید ☕️ "
            "ما انواع چای سیاه ایرانی داریم — از قلم و بهاره گرفته تا کَله‌مورچه‌ای و ممتاز. "
            "لطفاً بفرمایید دنبال چه نوع چایی هستید یا چه عطری را ترجیح می‌دهید؟"
        )
        print(f"🗣 عامل می‌گوید: {greeting}")
        await ctx.session.say(greeting, rate=0.9)
        self.state = "OFFERING"

    # ---------------- هنگام پاسخ مشتری ----------------
    async def on_user_spoke(self, ctx, text: str):
        text = text.strip()
        if not text:
            return

        if self.state == "OFFERING":
            self.customer["requests"].append(text)
            recommendations = (
                "بسیار عالی، بر اساس سلیقه‌ی شما پیشنهاد می‌کنم از چای‌های بهاره یا کَله‌مورچه‌ای استفاده کنید. "
                "بهاره عطر طبیعی گل دارد و کَله‌مورچه‌ای رنگ تیره و طعم‌تر.\n"
                "مایل هستید درباره‌ی تفاوت کیفیت و قیمتشان توضیح بدهم؟"
            )
            await ctx.session.say(recommendations, rate=0.9)
            self.state = "DETAILS"

        elif self.state == "DETAILS":
            # توضیح کیفیت‌ها
            detail_info = (
                "چای بهاره ممتاز هر کیلو حدود ۳۵۰ هزار تومان است و مخصوص فصل اول برداشت می‌باشد. "
                "چای کَله‌مورچه‌ای کمی قوی‌تر است و هر کیلو حدود ۴۰۰ هزار تومان قیمت دارد. "
                "چای قلم و ساقه اقتصادی‌تر هستند و برای مصرف روزانه مناسب‌اند.\n"
                "مایل هستید یکی از این گزینه‌ها را برای سفارش انتخاب کنم؟"
            )
            await ctx.session.say(detail_info, rate=0.9)
            self.state = "ORDER_REQUEST"

        elif self.state == "ORDER_REQUEST":
            self.customer["chosen_tea"] = text
            confirm = (
                f"خیلی خب، سفارش شما برای «{self.customer['chosen_tea']}» ثبت شد. "
                "لطفاً وزن یا مقدار مورد نظر را هم بفرمایید تا فاکتور آماده شود."
            )
            await ctx.session.say(confirm, rate=0.9)
            self.state = "ORDER_CONFIRM"

        elif self.state == "ORDER_CONFIRM":
            self.customer["requests"].append(text)
            closing = (
                "سپاس از خریدتان 🌿 سفارش شما با موفقیت ثبت شد. "
                "امیدوارم عطرو طعم چای‌ تازه چلچله‌سار روزتان را دل‌انگیز کند. "
                "به امید دیدار دوباره!"
            )
            await ctx.session.say(closing, rate=0.9)

            # ذخیره خلاصه‌ سفارش
            await self.save_summary(ctx)
            self.state = "CLOSE"

    # ---------------- ذخیره خلاصه مکالمه ----------------
    async def save_summary(self, ctx):
        summary_text = json.dumps(self.customer, ensure_ascii=False, indent=4)
        summarized = await self.summarize_text(ctx, summary_text)

        data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "conversation": self.customer,
            "summary": summarized,
        }

        with open("tea_shop_session_fa.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print("✅ خلاصه خرید در فایل tea_shop_session_fa.json ذخیره شد.")


# ======================================================
# ENTRYPOINT
# ======================================================
async def entrypoint(ctx: agents.JobContext):
    """راه‌اندازی کامل عامل صوتی چای‌خانه فارسی."""
    session = agents.AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe", language="fa"),
        llm=openai.LLM(model=os.getenv("LLM_CHOICE", "gpt-4.1-mini")),
        tts=openai.TTS(voice="sage"),   # بهترین صدای فعلی
        vad=silero.VAD.load(),
    )

    await session.start(room=ctx.room, agent=TeaShopAgentFA())


# ======================================================
# اجرای عامل
# ======================================================
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
