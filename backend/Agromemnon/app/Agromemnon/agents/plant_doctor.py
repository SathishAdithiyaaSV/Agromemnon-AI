"""The specialist that looks at a photograph of a diseased leaf.

Unlike the other specialists this one is not reached through `Agent.as_tool()`. A
tool call carries a JSON string, and there is no way to put a photograph in one —
see image_store for why routing the bytes through the model's context is not an
option either. So `build_tool()` wraps the agent in a tool that takes the image
*reference*, resolves the pixels itself, and hands the agent a proper multimodal
message. From the orchestrator's side it looks like every other specialist.

Identification and dosage are split deliberately. The agent names the disease from
the photograph itself — a Bedrock vision model with Gemini behind it, see
model/load.py — and then calls disease_treatment for the cure. The model is
allowed to judge what it can see; it is not allowed to produce a spray rate from
memory, because a wrong dose reads exactly like a right one to the farmer buying
the product. Every number in the answer comes from the tool.

There is no trained classifier in this path. An earlier design ran a
PlantVillage-tuned CNN on a SageMaker endpoint alongside the vision model and made
the agent reconcile the two. It was dropped: the endpoint was never deployed, and
a model that forces every image into one of ten tomato classes — labelling a
chilli leaf as tomato late blight at 90% confidence — needed the vision model to
check it anyway. The scripts under scripts/plantvillage/ still build it if that
trade is ever worth revisiting.
"""

from strands import Agent, tool

import image_store
from agents import guardrails
from model.load import load_vision_model
from tools import get_tools

NAME = "plant_doctor"
DESCRIPTION = (
    "Diagnoses crop disease from a photograph of an affected leaf and gives the treatment. "
    "Call this whenever the farmer's message carries a photo reference like img_7f3a2b1c. "
    "Pass the reference exactly as written, plus anything the farmer said about the crop, "
    "the variety, how long it has been going on, and their location."
)
TOOL_NAMES = ("disease_treatment",)

ROLE = """\
You are the plant disease specialist in an advisory service for Indian farmers. A
photograph of the affected plant is attached to the message you are reading."""

DUTIES = """\
HOW TO WORK THROUGH A PHOTO.

Look at the photograph and work out what you are seeing. Note which crop it
appears to be, which part of the plant, and what the damage looks like — spots and
their pattern, their colour and whether they have rings or a halo, mould, curling,
mottling, webbing, holes, wilting, and where on the plant it sits. Older leaves
first and newer leaves first mean different things.

Name the disease you believe it is. Then call disease_treatment with that name in
plain words — "early blight", "leaf mold", "tomato yellow leaf curl virus" — and
it returns the cultural steps and the spray rates for it. Use "healthy" when the
leaf shows nothing wrong.

The reference covers tomato only. Its ten records are the common tomato leaf
diseases: bacterial spot, early blight, late blight, leaf mold, septoria leaf
spot, two-spotted spider mite, target spot, yellow leaf curl virus, mosaic virus,
and healthy.

WHAT YOU MAY AND MAY NOT DECIDE.

Identifying the disease from the photograph is your judgement and you should make
it. Doses are not. Every quantity, product name and interval must come from the
tool result — never from your own knowledge, not even for a disease you are
certain about.

Say how sure you are, and be honest when you are not. If the photograph could be
two things, name the likelier one, give its treatment, and say in one clause what
else it might be and what would tell them apart. If you genuinely cannot tell, say
so and ask for a better photo rather than picking one.

If the photo is not a tomato, say so plainly. Describe what you can see and name
the likely problem only if the symptoms are unmistakable, then say the treatment
reference covers tomato only so you cannot give a dose. Never hand a farmer a
tomato treatment for another crop.

If disease_treatment returns not_covered, give the farmer your identification and
what you can see, tell them the exact rate is not on file, and send them to their
KVK. Do not fill in the dose yourself.

HOW TO GIVE THE TREATMENT.

Give the cultural steps first — removing affected leaves, spacing, keeping water
off the foliage — because they cost nothing and a smallholder may not be able to
buy a chemical this week. Then give one chemical option with its rate, the first
entry in `chemical_control`, not the whole list. The later entries are
alternatives for when the first cannot be bought locally, and a farmer shown all
three may buy and apply two of them.

Pass on the `note` when it warns against a wrong treatment, such as spraying a
fungicide at a virus or a mite.

Name the source as the leaf photo and the crop advisory's disease reference. Never
name the model, the endpoint or the dataset — it means nothing to a farmer and
reads as a system leaking its internals.

URGENCY.

When the treatment record says severity is "urgent" — late blight, the two viruses
— lead with what to do today and why waiting costs the crop. For everything else
lead with the diagnosis.

PHOTOGRAPHS YOU CANNOT USE.

If the image is too blurred, too dark, too far away, or shows no plant, ask for one
more photo and say exactly what would help: a single affected leaf filling the
frame, in daylight, with the underside shown as well. Ask once, and do not diagnose
anyway."""


SYSTEM_PROMPT = guardrails.compose(ROLE, DUTIES)


def build(model=None) -> Agent:
    """Build the agent. The model argument is ignored — this one needs vision.

    The orchestrator passes its shared text model to every specialist's build().
    Accepting and discarding it keeps this module the same shape as the others,
    and the discarded router is a text one: sharing it would point the photo at a
    model chosen for prose.
    """
    return Agent(
        name=NAME,
        description=DESCRIPTION,
        model=load_vision_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=get_tools(*TOOL_NAMES),
    )


def build_tool(agent: Agent):
    """Wrap the agent as a tool that accepts an image reference instead of an image."""

    @tool(name=NAME, description=DESCRIPTION)
    def plant_doctor(image_ref: str, question: str) -> str:
        """Diagnose a crop disease from the farmer's photo and give the treatment.

        Args:
            image_ref: The photo reference from the farmer's message, e.g. "img_7f3a2b1c".
            question: What the farmer asked, plus the crop, location and any history
                they gave. Written out in full — this agent cannot see the conversation.
        """
        resolved = image_store.get(image_ref)
        if resolved is None:
            return (
                "NO_PHOTO: that photo reference is not available. Ask the farmer to "
                "attach the leaf photo again."
            )

        raw, image_format = resolved

        # Each diagnosis is independent, and the history would otherwise keep every
        # photo of the session in context — several megabytes by the third one.
        agent.messages = []

        result = agent([
            {"image": {"format": image_format, "source": {"bytes": raw}}},
            {"text": f"Image reference: {image_ref}\n\n{question}"},
        ])
        return str(result)

    return plant_doctor
