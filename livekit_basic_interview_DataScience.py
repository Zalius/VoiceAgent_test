"""
OnTime Interview Voice Assistant
================================
An English-speaking LiveKit voice agent for conducting structured job interviews
for OnTime Company. Reads the candidate's resume, speaks professionally,
asks HR and technical questions, saves interview summary, then ends politely.

Requires OpenAI and Deepgram credentials in `.env`.
"""

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, RunContext
from livekit.agents.llm import function_tool
from livekit.plugins import openai, deepgram, silero
from datetime import datetime
import json
import os

# ---------------------
# Environment Setup
# ---------------------
load_dotenv(".env")


class OnTimeInterviewAgent(Agent):
    """Professional English-speaking interviewer agent for OnTime Company."""

    def __init__(self):
        super().__init__(
            instructions="""
You are an HR interviewer for OnTime Company speaking in a serious, clear tone.
Ask about resume details, recent projects, technical experience, and data-science concepts.
Keep your style direct, professional, and respectful.
"""
        )

        # Candidate example resume data
        self.resume = {
            "name": "Pooyan Alavi",
            "education": {
                "degree": "Master of Science",
                "major": "Computer Science",
                "university": "Amirkabir University of Technology",
                "year": "2022"
            },
            "experience": [
                {
                    "role": "Data Scientist",
                    "company": "DataMind Solutions",
                    "duration": "2022–2024",
                    "focus": "Developed predictive models with Python and TensorFlow"
                },
                {
                    "role": "Front-End Developer",
                    "company": "TechBridge Studio",
                    "duration": "2020–2021",
                    "focus": "Built dashboards in React and TypeScript"
                }
            ],
            "skills": [
                "Python", "TensorFlow", "React", "TypeScript", "SQL", "Docker", "Kubernetes"
            ]
        }

        self.interview_summary = None

    # ---------------------
    # Conversation Tools
    # ---------------------
    @function_tool
    async def load_resume_summary(self, context: RunContext) -> str:
        """Return a summary of resume for conversation bootstrapping."""
        r = self.resume
        text = (
            f"Candidate name: {r['name']}. "
            f"Education: {r['education']['degree']} in {r['education']['major']} "
            f"from {r['education']['university']} in {r['education']['year']}. "
            "Key experiences include working as Data Scientist and Front-End Developer. "
            f"Skills are: {', '.join(r['skills'])}."
        )
        return text

    @function_tool
    async def save_interview_summary(self, context: RunContext, notes: str) -> str:
        """Store interview notes/summary on disk."""
        summary = {
            "candidate": self.resume["name"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "skills": self.resume["skills"],
            "notes": notes,
            "result": "pending"
        }
        with open("pooyan_alavi_interview_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=4)
        self.interview_summary = summary
        return "Interview summary saved successfully."


# ---------------------
# LiveKit Entrypoint
# ---------------------
async def entrypoint(ctx: agents.JobContext):
    """Initialize the OnTime interview voice agent."""
    session = AgentSession(
        stt=deepgram.STT(model="nova-2"),  # English real-time streaming
        llm=openai.LLM(model=os.getenv("LLM_CHOICE", "gpt-4.1-mini")),
        tts=openai.TTS(voice="verse"),     # serious male voice
        vad=silero.VAD.load(),
    )

    # Launch the voice I/O session (this activates mic & speaker)
    await session.start(room=ctx.room, agent=OnTimeInterviewAgent())

    # Start interview greetings via TTS
    await session.generate_reply(
        instructions=(
            "Greet Pooyan Alavi politely. Then begin with: "
            "'Tell me about your experiences across different roles and companies.'"
        )
    )


# ---------------------
# Run as LiveKit Worker
# ---------------------
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
