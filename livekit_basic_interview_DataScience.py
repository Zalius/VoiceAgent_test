"""
Enhanced OnTime Interview Assistant
Structured turn-based voice interview that first asks
about education, waits for response, and then continues
with experience and technical questions.
"""

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent
from livekit.agents.events import * # type: ignore
from livekit.plugins import openai
from datetime import datetime
import json

load_dotenv(".env")


class OnTimeInterviewAgent(Agent):
    """Turn-based voice interviewer for OnTime Company."""

    def __init__(self):
        super().__init__(
            instructions=(
                "You are a formal HR interviewer for OnTime Company. "
                "Speak in a serious, respectful tone. "
                "Follow structured phases: Greeting → Education → Experience → Technical → Closing."
            )
        )
        self.state = "GREETING"
        self.resume = {
            "name": "Pooyan Alavi",
            "education": "Master of Science in Computer Science from Amirkabir University of Technology (2022)",
            "experience": [
                "Data Scientist at DataMind Solutions (2022–2024)",
                "Front-End Developer at TechBridge Studio (2020–2021)",
            ],
            "skills": ["Python", "TensorFlow", "React", "TypeScript", "SQL", "Docker", "Kubernetes"]
        }
        self.user_answers = {}

    async def on_start(self, ctx):
        """Called once when room connection established."""
        await ctx.session.say(
            f"Hello {self.resume['name']}, thank you for joining this interview for OnTime Company. "
            "Let's begin with your academic background. Could you please tell me about your education?"
        )
        self.state = "EDUCATION"

    async def on_user_spoke(self, ctx, text: str):
        """Triggered whenever user finishes speaking (STT transcript available)."""
        if self.state == "EDUCATION":
            self.user_answers["education"] = text
            await ctx.session.say(
                "Excellent. Now let's talk about your work experience. "
                "Could you describe your experiences across different roles and companies?"
            )
            self.state = "EXPERIENCE"

        elif self.state == "EXPERIENCE":
            self.user_answers["experience"] = text
            await ctx.session.say(
                "Thank you. Now let's discuss some technical points. "
                "Can you explain how RNN and LSTM architectures differ, and what makes CNNs effective for images?"
            )
            self.state = "TECH"

        elif self.state == "TECH":
            self.user_answers["technical"] = text
            await ctx.session.say(
                "Thank you for sharing your insights. "
                "That concludes our interview. We'll review your responses and contact you soon. Goodbye."
            )
            await self.save_summary()
            self.state = "CLOSE"

    async def save_summary(self):
        summary = {
            "candidate": self.resume["name"],
            "timestamp": datetime.now().isoformat(),
            "answers": self.user_answers,
        }
        with open("pooyan_alavi_interview_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=4)


# ------------------- ENTRYPOINT -------------------

async def entrypoint(ctx):
    session = agents.AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe", language="en"),
        llm=openai.LLM(model="gpt-4.1-mini"),
        tts=openai.TTS(voice="verse"),
    )
    await session.start(room=ctx.room, agent=OnTimeInterviewAgent())


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
