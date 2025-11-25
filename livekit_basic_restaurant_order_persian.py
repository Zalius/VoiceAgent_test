"""
Restaurant Persian Voice Assistant
==================================
A LiveKit Persian-speaking voice agent for taking food orders.
All system messages and conversation are in Persian,
but function and variable names remain standard English.
Requires OpenAI and Deepgram API keys.
"""

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, RunContext
from livekit.agents.llm import function_tool
from livekit.plugins import openai, deepgram, silero
from datetime import datetime
import os


# Load environment variables
load_dotenv(".env")


class PersianRestaurantAgent(Agent):
    """Persian-speaking restaurant phone operator."""

    def __init__(self):
        super().__init__(
            instructions="""شما اپراتور تلفنی گرم و محترمانه‌ی رستوران چلچله سار هستید.
            با مشتری به فارسی صحبت کنید، سفارش بگیرید، جزئیات را تأیید کنید،
            آدرس تحویل را بپرسید و در پایان از او تشکر نمایید."""
        )

        # Menu (English keys, Persian content)
        self.menu = {
            "burgers": {
                "برگر کلاسیک": {"price": 230_000, "options": ["پنیر اضافه", "بیکن", "کاهو بیشتر"]},
                "برگر مرغ": {"price": 250_000, "options": ["مایونز بیشتر", "تخم‌مرغ", "پنیر"]},
                "برگر سبزیجات": {"price": 220_000, "options": ["آووکادو", "سس تند", "گوجه اضافی"]},
            },
            "pizza": {
                "پیتزا مخلوط": {"price": 340_000, "options": ["پنیر اضافه", "قارچ", "زیتون"]},
                "پیتزا پپرونی": {"price": 360_000, "options": ["پپرونی بیشتر", "لبه پُر پنیر", "زیتون"]},
                "پیتزا مرغ و باربیکیو": {"price": 370_000, "options": ["سس بیشتر", "فلفل هالاپینو", "پیاز"]},
            },
            "fries": {
                "سیب‌زمینی ساده": {"price": 110_000, "options": ["کچاپ", "سس پنیر", "مایونز"]},
                "سیب‌زمینی پیچ‌دار": {"price": 130_000, "options": ["باربیکیو", "رنچ"]},
            },
            "drinks": {
                "نوشابه": {"price": 60_000, "options": ["یخ", "بدون یخ"]},
                "آب پرتقال": {"price": 90_000, "options": ["بدون پالپ", "خیلی سرد"]},
                "آب معدنی": {"price": 40_000, "options": ["دمای محیط", "سرد"]},
            },
            "desserts": {
                "کیک شکلاتی": {"price": 150_000, "options": ["فاج بیشتر", "خامه"]},
                "بستنی": {"price": 120_000, "options": ["شکلات", "اسپرینکلز"]},
            },
        }

        self.orders = []
        self.customer_name = None
        self.delivery_address = None

    # ---------------------
    # Functional tools
    # ---------------------

    @function_tool
    async def view_menu(self, context: RunContext) -> str:
        """Show Persian menu items."""
        msg = "📋 منوی امروز ما:\n\n"
        for cat, items in self.menu.items():
            msg += f"{cat.title()}:\n"
            for name, info in items.items():
                msg += f"  • {name} - {info['price']:,} تومان\n"
            msg += "\n"
        msg += "هر غذا را می‌خواهید، فقط نامش را بگویید تا اضافه کنم."
        return msg

    @function_tool
    async def add_item(self, context: RunContext, category: str, item_name: str, quantity: int = 1, options: list[str] | None = None) -> str:
        """Add item to current order."""
        cat = category.lower()
        if cat not in self.menu or item_name not in self.menu[cat]:
            return f"با عرض پوزش، '{item_name}' در منوی {category} وجود ندارد."

        item = self.menu[cat][item_name]
        total = item["price"] * quantity
        opts = options or []
        self.orders.append({"item": item_name, "quantity": quantity, "options": opts, "total": total})
        opts_text = f" با {' و '.join(opts)}" if opts else ""
        return f"{quantity} عدد {item_name}{opts_text} اضافه شد. جمع فعلی {total:,} تومان."

    @function_tool
    async def view_order(self, context: RunContext) -> str:
        """List current order summary."""
        if not self.orders:
            return "هنوز چیزی سفارش نداده‌اید."
        text = "📦 خلاصه سفارش:\n\n"
        total = 0
        for o in self.orders:
            text += f"• {o['quantity']} × {o['item']} - {o['total']:,} تومان"
            if o['options']:
                text += f" با {', '.join(o['options'])}"
            text += "\n"
            total += o['total']
        text += f"\nجمع کل تا الان: {total:,} تومان"
        return text

    @function_tool
    async def set_address(self, context: RunContext, address: str) -> str:
        """Save delivery address."""
        self.delivery_address = address
        return f"آدرس شما ثبت شد: {address}"

    @function_tool
    async def confirm_order(self, context: RunContext, customer_name: str) -> str:
        """Confirm final order and produce receipt."""
        if not self.orders:
            return "ابتدا لطفاً چیزی سفارش دهید."
        if not self.delivery_address:
            return "آدرس ارسال را لطفاً اعلام کنید."

        total = sum(o["total"] for o in self.orders)
        order_id = f"ORD{1000 + len(self.orders)}"
        result = f"✅ سفارش شما ثبت شد!\n"
        result += f"کد سفارش: {order_id}\n"
        result += f"نام مشتری: {customer_name}\n"
        result += f"آدرس: {self.delivery_address}\n\n"
        result += "اقلام:\n"
        for o in self.orders:
            result += f"  - {o['quantity']} × {o['item']} ({o['total']:,} تومان)\n"
        result += f"\nمجموع قابل پرداخت: {total:,} تومان\n"
        result += "\nبا تشکر از انتخاب رستوران ما 🌸"
        return result

    @function_tool
    async def current_time(self, context: RunContext) -> str:
        """Return current time in Persian format."""
        now = datetime.now().strftime("%H:%M - %Y/%m/%d")
        return f"ساعت اکنون {now} است."


# ---------------------
# LiveKit Entrypoint
# ---------------------

async def entrypoint(ctx: agents.JobContext):
    """Initialize Persian-speaking restaurant assistant."""
    session = AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe", language="fa"),
        llm=openai.LLM(model=os.getenv("LLM_CHOICE", "gpt-4.1-mini")),
        tts=openai.TTS(voice="alloy"),
        vad=silero.VAD.load(),
    )

    await session.start(room=ctx.room, agent=PersianRestaurantAgent())

    await session.generate_reply(
        instructions="با لحن صمیمی سلام کنید و بپرسید چه غذایی میل دارند."
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
