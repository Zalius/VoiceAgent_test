"""
عامل مصاحبه پیشرفته شرکت OnTime - نسخه بهبود یافته v3
================================================================
"""

import asyncio
import logging
from dotenv import load_dotenv
import os, json, re
from datetime import datetime

load_dotenv()

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import openai, silero
from livekit import rtc

logger = logging.getLogger("interview-agent")
logger.setLevel(logging.INFO)


class OnTimeInterviewAgent(Agent):
    """مصاحبه‌گر حرفه‌ای با کنترل کامل جریان"""

    def __init__(self):
        super().__init__(
            instructions=(
                "شما مصاحبه‌گر رسمی و حرفه‌ای شرکت OnTime هستید که به زبان فارسی صحبت می‌کنید. "
                "شما فقط و فقط سوالات از پیش تعیین شده مصاحبه را می‌پرسید. "
                "اگر کاربر سوال دیگری پرسید یا موضوع دیگری مطرح کرد، محترمانه اما قاطعانه او را به موضوع اصلی مصاحبه برگردانید. "
                "هرگز به سوالات خارج از چارچوب مصاحبه پاسخ ندهید. "
                "از کاربر برای پاسخ‌هایش تشکر کنید و فوراً به سوال بعدی بروید. "
                "پاسخ‌های شما کوتاه، رسمی و مستقیم باشد. هیچ توضیح اضافی ندهید."
            )
        )
        
        self.state = "INIT"
        self.candidate = {
            "name": None,
            "age": None,
            "location": None,
            "education": None,
            "experience": None,
            "hr_answers": [],
            "technical_answers": []
        }

        self.hr_questions = [
            "چرا دوست دارید در شرکت ما کار کنید؟",
            "سه سال آینده خودتان را در چه موقعیتی می‌بینید؟",
            "مهم‌ترین اولویت شما در انتخاب محیط کار چیست؟"
        ]
        
        self.tech_questions = [
            "تفاوت اساسی بین شبکه‌های RNN و LSTM را توضیح دهید.",
            "چرا شبکه‌های کانولوشنال در پردازش تصویر کارآمد هستند؟",
            "اهمیت نرمال‌سازی داده در یادگیری ماشین چیست؟",
            "تفاوت یادگیری نظارت‌شده و بدون‌نظارت را شرح دهید."
        ]
        
        self.hr_index = 0
        self.tech_index = 0
        self.retry_count = 0
        self.off_topic_count = 0


    def detect_off_topic(self, text: str) -> bool:
        """تشخیص سوالات خارج از مصاحبه"""
        off_topic_patterns = [
            r"چطور.*می‌?تون",
            r"چجوری",
            r"آیا.*می‌?دون",
            r"می‌?شه.*بگ",
            r"می‌?شه.*کمک",
            r"لطفا.*توضیح.*بد",
            r"سوال.*دار",
            r"می‌?خواستم.*بپرس",
            r"یه.*سوال",
            r"یک.*سوال",
            r"راستی",
            r"ببخشید.*چطور",
            r"می‌?تونی.*بگی",
        ]
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in off_topic_patterns)


    def is_answer_sufficient(self, text: str, min_words: int = 5) -> bool:
        """بررسی کفایت پاسخ"""
        words = [w for w in text.split() if len(w) > 1]
        if len(words) < min_words:
            return False
        
        insufficient = ["نمی.*دون", "نمیدون", "^خیر$", "^نه$", "^رد$", "نمی‌دونم"]
        return not any(re.search(p, text.lower()) for p in insufficient)


    async def handle_off_topic_response(self, session) -> str:
        """پاسخ به موضوعات نامرتبط"""
        self.off_topic_count += 1
        
        responses = [
            "متوجه هستم، اما الان در حال مصاحبه هستیم. لطفاً فقط به سوالات مصاحبه پاسخ دهید.",
            "من فقط مجاز به انجام مصاحبه هستم. بیایید روی سوالات مصاحبه تمرکز کنیم.",
            "لطفاً به روند مصاحبه ادامه دهیم."
        ]
        
        idx = min(self.off_topic_count - 1, len(responses) - 1)
        return responses[idx]


    async def on_start(self, session: AgentSession):
        """شروع مصاحبه"""
        logger.info("🎤 شروع مصاحبه")
        self.state = "GREETING"
        
        greeting = (
            "سلام و درود. به مصاحبه شرکت آن‌تایم خوش آمدید. "
            "من مصاحبه‌گر این جلسه هستم. "
            "لطفاً نام و نام‌خانوادگی کامل خود را بفرمایید."
        )
        
        await session.say(greeting, allow_interruptions=True)
        self.state = "ASK_NAME"


    async def on_user_spoke(self, session: AgentSession, text: str):
        """پردازش گفتار کاربر"""
        text = text.strip()
        if not text:
            return

        logger.info(f"👤 [{self.state}] کاربر گفت: {text[:100]}")

        # تشخیص خروج از موضوع (جز در سوالات ساده)
        if self.state not in ["ASK_NAME", "ASK_AGE", "ASK_LOCATION"] and self.detect_off_topic(text):
            response = await self.handle_off_topic_response(session)
            await session.say(response, allow_interruptions=False)
            
            # تکرار سوال فعلی
            if self.state == "HR_STAGE" and self.hr_index < len(self.hr_questions):
                await session.say(self.hr_questions[self.hr_index], allow_interruptions=True)
            elif self.state == "TECH_STAGE" and self.tech_index < len(self.tech_questions):
                await session.say(self.tech_questions[self.tech_index], allow_interruptions=True)
            return

        # ============= مراحل مصاحبه =============
        
        # نام
        if self.state == "ASK_NAME":
            self.candidate["name"] = text
            self.off_topic_count = 0
            await session.say("متشکرم. سن شما چند سال است؟", allow_interruptions=True)
            self.state = "ASK_AGE"
            return

        # سن
        elif self.state == "ASK_AGE":
            self.candidate["age"] = text
            self.off_topic_count = 0
            await session.say("سپاس. محل سکونت فعلی شما کجاست؟", allow_interruptions=True)
            self.state = "ASK_LOCATION"
            return

        # محل سکونت
        elif self.state == "ASK_LOCATION":
            self.candidate["location"] = text
            self.off_topic_count = 0
            await session.say(
                "بسیار خوب. لطفاً آخرین مدرک تحصیلی و رشته تحصیلی خود را بیان کنید.",
                allow_interruptions=True
            )
            self.state = "ASK_EDUCATION"
            return

        # تحصیلات
        elif self.state == "ASK_EDUCATION":
            self.candidate["education"] = text
            self.off_topic_count = 0
            await session.say(
                "ممنون. لطفاً خلاصه‌ای از سوابق کاری و پروژه‌های مهم خود ارائه دهید.",
                allow_interruptions=True
            )
            self.state = "ASK_EXPERIENCE"
            return

        # تجربه کاری
        elif self.state == "ASK_EXPERIENCE":
            if not self.is_answer_sufficient(text, min_words=8):
                if self.retry_count < 1:
                    self.retry_count += 1
                    await session.say(
                        "لطفاً کمی بیشتر توضیح دهید. مثلاً چه پروژه‌هایی انجام داده‌اید؟",
                        allow_interruptions=True
                    )
                    return
            
            self.candidate["experience"] = text
            self.retry_count = 0
            self.off_topic_count = 0
            await session.say(
                "بسیار خوب. حالا وارد بخش سوالات منابع انسانی می‌شویم.",
                allow_interruptions=False
            )
            await asyncio.sleep(0.5)
            await session.say(self.hr_questions[0], allow_interruptions=True)
            self.state = "HR_STAGE"
            return

        # بخش HR
        elif self.state == "HR_STAGE":
            skip_keywords = ["رد", "بعدی", "نمیدون", "نمی‌دون", "پاس", "skip"]
            is_skip = any(kw in text.lower() for kw in skip_keywords)
            
            if is_skip:
                await session.say("بسیار خوب، می‌رویم سوال بعدی.", allow_interruptions=False)
            else:
                if not self.is_answer_sufficient(text, min_words=6):
                    if self.retry_count < 1:
                        self.retry_count += 1
                        await session.say(
                            "ممکن است کمی بیشتر شرح دهید؟",
                            allow_interruptions=True
                        )
                        return
                
                self.candidate["hr_answers"].append(text)
                await session.say("متشکرم.", allow_interruptions=False)
            
            self.retry_count = 0
            self.off_topic_count = 0
            self.hr_index += 1
            
            if self.hr_index < len(self.hr_questions):
                await asyncio.sleep(0.3)
                await session.say(self.hr_questions[self.hr_index], allow_interruptions=True)
            else:
                await session.say(
                    "عالی. اکنون وارد بخش سوالات فنی می‌شویم.",
                    allow_interruptions=False
                )
                await asyncio.sleep(0.5)
                await session.say(self.tech_questions[0], allow_interruptions=True)
                self.state = "TECH_STAGE"
            return

        # بخش فنی
        elif self.state == "TECH_STAGE":
            skip_keywords = ["رد", "بعدی", "نمیدون", "نمی‌دون", "پاس", "skip"]
            is_skip = any(kw in text.lower() for kw in skip_keywords)
            
            if is_skip:
                await session.say("متوجه هستم. سوال بعدی.", allow_interruptions=False)
            else:
                if not self.is_answer_sufficient(text, min_words=8):
                    if self.retry_count < 1:
                        self.retry_count += 1
                        await session.say(
                            "لطفاً با جزئیات بیشتری توضیح دهید.",
                            allow_interruptions=True
                        )
                        return
                
                self.candidate["technical_answers"].append(text)
                await session.say("سپاس‌گزارم.", allow_interruptions=False)
            
            self.retry_count = 0
            self.off_topic_count = 0
            self.tech_index += 1
            
            if self.tech_index < len(self.tech_questions):
                await asyncio.sleep(0.3)
                await session.say(self.tech_questions[self.tech_index], allow_interruptions=True)
            else:
                await session.say(
                    "مصاحبه به پایان رسید. از وقتی که گذاشتید متشکرم. "
                    "نتیجه را در اسرع وقت به اطلاع شما خواهیم رساند. "
                    "می‌توانید تماس را قطع کنید.",
                    allow_interruptions=False
                )
                self.state = "FINISHED"
                await self.save_interview_data(session)
            return


    async def save_interview_data(self, session: AgentSession):
        """ذخیره داده‌های مصاحبه"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name_safe = self.candidate.get('name', 'unknown').replace(' ', '_')
            
            output = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "candidate": self.candidate,
                "metadata": {
                    "total_hr_questions": len(self.hr_questions),
                    "hr_answered": len(self.candidate["hr_answers"]),
                    "total_tech_questions": len(self.tech_questions),
                    "tech_answered": len(self.candidate["technical_answers"])
                }
            }
            
            filename = f"interview_{name_safe}_{timestamp}.json"
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ مصاحبه ذخیره شد: {filename}")
            
        except Exception as e:
            logger.error(f"❌ خطا در ذخیره: {e}")


async def entrypoint(ctx: JobContext):
    """نقطه ورود عامل"""
    logger.info("⏳ اتصال به اتاق LiveKit...")
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    logger.info(f"✅ عامل متصل شد به اتاق: {ctx.room.name}")

    # Event handlers برای دیباگ
    @ctx.room.on("track_subscribed")
    def on_track(track: rtc.Track, publication, participant):
        logger.info(f"🎵 Track subscribed: {track.kind} از {participant.identity}")

    participant = await ctx.wait_for_participant()
    logger.info(f"🎤 شرکت‌کننده وارد شد: {participant.identity}")

    agent = OnTimeInterviewAgent()
    
    session = AgentSession(
        stt=openai.STT(
            model="gpt-4o-transcribe",
            language="fa",
        ),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="alloy"),
        vad=silero.VAD.load(
            min_speech_duration=0.2,
            min_silence_duration=0.5,
        ),
    )

    # Event handlers برای session
    @session.on("user_started_speaking")
    def on_speaking():
        logger.info("🗣️ کاربر شروع به صحبت کرد")

    @session.on("user_stopped_speaking")
    def on_stopped():
        logger.info("🤐 کاربر ساکت شد")

    await session.start(agent=agent, room=ctx.room)
    
    await agent.on_start(session)
    
    await asyncio.Future()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
