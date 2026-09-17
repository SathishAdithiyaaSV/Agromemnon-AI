from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager

from agents import crop_agent, irrigation_agent, scheme_adviser
from model.load import load_model

# Add a new specialist by writing agents/<name>.py with a build(model) function and
# listing its module here — the orchestrator exposes each one as a tool.
SUB_AGENTS = (scheme_adviser, crop_agent, irrigation_agent)

SYSTEM_PROMPT = """You are Agromemnon, an agricultural advisory assistant for farmers.

Each specialist agent is available to you as a tool. Route a question to the specialists
whose area it falls in, and call several when it spans more than one, then combine their
answers into a single reply. Handle greetings and small talk yourself.
"""


def build() -> Agent:
    model = load_model()
    return Agent(
        name="orchestrator",
        description="Routes farmer questions to the specialist agents and combines their answers.",
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[module.build(model).as_tool() for module in SUB_AGENTS],
        conversation_manager=NullConversationManager(),
    )
