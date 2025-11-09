"""
OnTime Voice Interview Agent — Production Version
=================================================
Interactive real‑time voice interviewer for OnTime Company.
Uses Deepgram STT + Silero VAD + OpenAI TTS + OpenAI LLM.
Interview flow: Greeting → Education → Experience → Technical → Closing.
"""

from dotenv import load_dotenv
import os
import json
from datetime import datetime

from livekit import agents
from livekit.agents import Agent
from livekit.plugins import deepgram, silero, openai


# ---------------------- ENV SETUP ----------------------
load_dotenv(".env")


# ======================================================
# MAIN AGENT CLASS
# ======================================================
class OnTimeInterviewAgent(Agent):
    """Professional, turn-based English-speaking interviewer agent."""

    def __init__(self):
        super().__init__(
            instructions=(
                "You are an HR interviewer for OnTime Company. "
                "Conduct a calm, serious, professional interview in English. "
                "Ask about education, wait for reply, then ask about work experience, "
                "then technical topics about data science, and end politely."
            )
        )

        # Interview finite-state machine
        self.state = "GREETING"

        # Resume-based context awareness
        self.resume = {
            "name": "Pooyan Alavi",
            "education": "Master of Science in Computer Science from Amirkabir University of Technology (2022)",
            "experience": [
                "Data Scientist at DataMind Solutions (2022–2024)",
                "Front-End Developer at TechBridge Studio (2020–2021)"
            ],
            "skills": ["Python", "TensorFlow", "React", "TypeScript", "SQL", "Docker", "Kubernetes"]
        }

        # Candidate responses to save later
        self.candidate = {
            "name": self.resume["name"],
            "education": None,
            "experience": None,
            "technical": None,
        }

    # ----------------- EVENT HANDLERS -----------------
    async def on_start(self, ctx):
        """Called once when microphone and room connected."""
        greeting = (
            f"Hello {self.resume['name']}, thank you for joining this interview for OnTime Company. "
            f"I see you earned your {self.resume['education']}. "
            "Could you please tell me more about your major and your academic focus?"
        )
        print(f"🗣 Agent says: {greeting}")
        await ctx.session.say(greeting, rate=0.9)
        self.state = "EDUCATION"

    async def on_user_spoke(self, ctx, text: str):
        """Triggered every time candidate stops speaking (silence detected by VAD)."""
        text = text.strip()
        if not text:
            return

        if self.state == "EDUCATION":
            # Save education section
            self.candidate["education"] = text
            follow_up = (
                "Excellent. Now let's talk about your professional journey. "
                f"I noticed you worked at {', '.join(self.resume['experience'])}. "
                "Could you describe your responsibilities and the technologies you used?"
            )
            print(f"🗣 Agent says: {follow_up}")
            await ctx.session.say(follow_up, rate=0.9)
            self.state = "EXPERIENCE"

        elif self.state == "EXPERIENCE":
            self.candidate["experience"] = text
            tech_question = (
                "Thank you for explaining your work background. "
                "Let's move to some technical questions. "
                "Can you explain the difference between RNN and LSTM, "
                "and what makes CNNs effective for image recognition?"
            )
            print(f"🗣 Agent says: {tech_question}")
            await ctx.session.say(tech_question, rate=0.9)
            self.state = "TECH"

        elif self.state == "TECH":
            self.candidate["technical"] = text
            closing = (
                "Thank you for sharing your insights. "
                "That concludes our interview. We’ll review your responses and contact you soon. Goodbye!"
            )
            print(f"🗣 Agent says: {closing}")
            await ctx.session.say(closing, rate=0.9)
            await self.save_summary()
            self.state = "CLOSE"

    # ----------------- UTILITIES -----------------
    async def save_summary(self):
        """Save all responses to JSON for later review."""
        summary = {
            "candidate": self.candidate["name"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "education": self.candidate["education"],
            "experience": self.candidate["experience"],
            "technical": self.candidate["technical"],
        }
        with open("pooyan_alavi_interview_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=4)
        print("✅ Interview summary saved to pooyan_alavi_interview_summary.json")


# ======================================================
# ENTRYPOINT
# ======================================================
async def entrypoint(ctx: agents.JobContext):
    """Bootstraps full live interactive session with mic/speaker."""
    session = agents.AgentSession(
        stt=deepgram.STT(model="nova-2"),    # real-time transcription
        vad=silero.VAD.load(),               # silence detection
        llm=openai.LLM(model="gpt-4.1-mini"),
        tts=openai.TTS(voice="verse"),       # steady, confident HR voice
    )

    await session.start(room=ctx.room, agent=OnTimeInterviewAgent())


# ======================================================
# WORKER: LAUNCH AGENT
# ======================================================
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
