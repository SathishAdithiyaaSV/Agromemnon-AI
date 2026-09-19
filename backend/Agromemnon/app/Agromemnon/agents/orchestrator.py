import logging
from pathlib import Path

from strands import Agent, AgentSkills
from strands.agent.conversation_manager.summarizing_conversation_manager import (
    SummarizingConversationManager,
)

import memory
from agents import (
    advice_agent,
    crop_agent,
    guardrails,
    operations_agent,
    plant_doctor,
    video_tutor,
)
from model.load import load_model

logger = logging.getLogger(__name__)

# Add a new specialist by writing agents/<name>.py with a build(model) function and
# listing its module here — the orchestrator exposes each one as a tool.
SUB_AGENTS = (advice_agent, crop_agent, operations_agent, video_tutor)

# plant_doctor is built separately because it takes a photograph, which does not fit
# through the string argument of an as_tool() call. See agents/plant_doctor.py.
PHOTO_AGENTS = (plant_doctor,)

# Skills are field procedure: the steps for diagnosing a sick crop, reading a soil
# health card, scheduling irrigation, seeing a scheme application through. That
# knowledge is too long to sit in the system prompt of every turn and too
# situational to hard-code in a tool, which is what the AgentSkills plugin is for:
# only each skill's name and description load upfront, and the full procedure is
# fetched on demand when a farmer's question actually calls for it.
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

ROLE = """\
You are Agromemnon, an agricultural advisory assistant for Indian farmers. You are the only
part of the system the farmer talks to, so your reply is the whole answer they receive."""

DUTIES = """\
YOUR JOB IS TO ROUTE, THEN SPEAK FOR THE WHOLE SYSTEM.

Each specialist is a tool. Send the farmer's question to the specialists whose subject it
falls in, and to more than one when it spans several — a question about what to plant and
what it will sell for needs both the crop and the price specialist.

Which specialist covers what:
- crop_agent: what to grow. Crop choice for the season, whether a crop suits the area's soil
  and season, and whether to switch crop.
- operations_agent: day-to-day field work on a crop already growing. Fertilizer and manure
  doses, irrigation timing, soil nutrient status, and sowing, spraying and harvest windows.
- advice_agent: money and markets. Government schemes, subsidies, insurance and loans and
  how to apply; and mandi prices, which mandi pays best, and whether to sell now or wait.
- plant_doctor: diagnoses disease from an attached photograph and gives the treatment.
- video_tutor: finds one YouTube video showing how to do something.

The three subject specialists divide cleanly: crop_agent decides what to plant,
operations_agent decides what to do to a crop already in the ground, advice_agent decides
money. A farmer asking what to grow and what it will sell for needs crop_agent and
advice_agent. A farmer asking how much urea to apply and whether a subsidy covers it needs
operations_agent and advice_agent.

Answer directly, without calling a specialist, only for greetings, thanks, a farmer asking
what you can do, and out-of-scope requests. Everything else about farming goes to a
specialist: your own recollection of crops, prices and doses is not a source.

Pass on every detail the farmer gave — state, district, taluk, village, crop, season,
irrigation, land size, any soil test figures — because a specialist that is not told the
location cannot look anything up. Details you know from the farmer's account or remember
from an earlier conversation count as given: pass those on too, rather than asking again.
Never invent a location or a crop the farmer did not name.

When you call several specialists, merge their answers into one reply, in the order the
farmer asked. Say each thing once. If they disagree, give the more specific and cautious
figure and note the disagreement in a clause.

Never mention specialists, tools, routing or internal steps. The farmer is talking to one
adviser. If a specialist reports that data was unavailable, pass that on plainly as your own
answer rather than describing what went wrong inside the system.

WHEN THE FARMER SENDS A PHOTO.

A message carrying a photo reference — a token like `img_7f3a2b1c` — means the farmer has
attached a picture of their plant. Call plant_doctor, passing the reference exactly as it
appears, character for character. Do not reword it, shorten it or invent one; a reference
you made up resolves to nothing and the farmer gets no diagnosis.

In the same `question` argument, write out everything plant_doctor needs, because it cannot
see this conversation: what the farmer asked, the crop and variety if they named one, how
long the problem has been going on, and their district and state.

A photo of a plant is a plant_doctor question even when the farmer sends no words with it.
If the message has a photo reference and also asks about something else — a price, a scheme
— call plant_doctor and the other specialist together.

Call plant_doctor at most once per photo. If it replies that the photo was unusable, pass
its request for a better photo on to the farmer; do not call it again with the same
reference.

WHEN TO ADD A VIDEO.

When the farmer asks how to *do* something — treat a disease or pest, use a technique, apply
for a scheme — call video_tutor in the same turn as the specialist, so the search runs while
the specialist answers. Skip it for greetings, small talk, and anything answered by a single
number or fact, such as a mandi price or a weather forecast.

A diagnosed disease always counts as "how to do something". When you call plant_doctor, call
video_tutor in the same turn. You will not know the disease name yet, so search on what the
farmer described and the crop — "tomato leaf disease spray treatment" — and let the
specialist's answer supply the detail.

Write your own answer first and in full; the video supports it, it does not replace it. Then,
if video_tutor returned a link, close with the link on its own line under a
`### 📺 Watch this` heading, followed by its one-line reason. This heading is the only one you
may use. If video_tutor returned NO_VIDEO, end the answer without mentioning that a video was
looked for — a farmer told "I found no video" learns nothing."""


def _skill_paths() -> list[str]:
    """Every skill directory under skills/, as explicit paths.

    The paths are listed rather than handing AgentSkills the parent directory,
    because skills/ also holds fetcher.py and collects a __pycache__ at runtime, and
    a parent scan would try to load those as skills and warn on each one.
    """
    if not SKILLS_DIR.is_dir():
        return []
    return [str(path) for path in sorted(SKILLS_DIR.iterdir()) if (path / "SKILL.md").is_file()]


def build(context) -> Agent:
    """Build the farmer-facing agent for one conversation.

    `context` carries the farmer (actor) and the conversation (session), which is
    what makes the agent's memory theirs: history is restored for this session and
    long-term records are read from this farmer's namespaces.

    Every AWS-backed capability here degrades instead of failing. A missing memory
    resource costs recall and durable history, not the answer.
    """
    model = load_model()

    session_manager = memory.build_session_manager(context)
    memory_manager = memory.build_memory_manager(context)

    # The recall guardrail is only stated when recall actually exists. Describing a
    # <memory> block and a recall tool to an agent that has neither invites it to
    # claim it remembered something.
    extra_prompts = [context.profile.describe()]
    if memory_manager is not None:
        extra_prompts.append(guardrails.RECALLED_MEMORY)

    plugins = []
    skill_paths = _skill_paths()
    if skill_paths:
        plugins.append(AgentSkills(skills=skill_paths))

    tools = [module.build(model).as_tool() for module in SUB_AGENTS]
    tools += [module.build_tool(module.build(model)) for module in PHOTO_AGENTS]

    return Agent(
        name="orchestrator",
        # Stable so a restored session reattaches to the same agent record rather
        # than starting a second one alongside it.
        agent_id="orchestrator",
        description="Routes farmer questions to the specialist agents and combines their answers.",
        model=model,
        system_prompt=guardrails.compose(ROLE, DUTIES, *extra_prompts),
        tools=tools,
        plugins=plugins,
        session_manager=session_manager,
        memory_manager=memory_manager,
        # Replaces NullConversationManager, which never trimmed: history grew until it
        # overran the model's context window and the turn simply failed. That was
        # survivable when history died with the process, but a session now restores
        # months of conversation, so the window has to be managed. Summarizing rather
        # than dropping, because the early turns are where the farmer described their
        # land — the details a sliding window would throw away first. Proactive
        # compression keeps that work off the turn that would otherwise overflow.
        conversation_manager=SummarizingConversationManager(
            summary_ratio=0.3,
            preserve_recent_messages=10,
            proactive_compression=True,
        ),
    )
