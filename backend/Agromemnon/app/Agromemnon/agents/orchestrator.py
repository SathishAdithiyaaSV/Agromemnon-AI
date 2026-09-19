from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager

from agents import crop_agent, irrigation_agent, scheme_adviser, video_tutor
from model.load import load_model

# Add a new specialist by writing agents/<name>.py with a build(model) function and
# listing its module here — the orchestrator exposes each one as a tool.
SUB_AGENTS = (scheme_adviser, crop_agent, irrigation_agent, video_tutor)

SYSTEM_PROMPT = """You are Agromemnon, an agricultural advisory assistant for farmers.

Each specialist agent is available to you as a tool. Route a question to the specialists
whose area it falls in, and call several when it spans more than one, then combine their
answers into a single reply. Handle greetings and small talk yourself.

When the farmer asks how to do something — treat a disease or pest, use a technique,
apply for a scheme — call video_tutor in the same turn as the specialist, so the search
runs while the specialist answers. Skip it for greetings, small talk, and questions
answered by a number or a fact, such as a mandi price or a weather forecast.

Write your own answer first and in full; the video supports it, it does not replace it.
Then, if video_tutor returned a link, close with the link on its own line under a
`### 📺 Watch this` heading, followed by its one-line reason. If it returned NO_VIDEO,
end the answer without mentioning that a video was looked for.
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
