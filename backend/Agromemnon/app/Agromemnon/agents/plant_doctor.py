"""The specialist that looks at a photograph of a diseased leaf.

Unlike the other specialists this one is not reached through `Agent.as_tool()`. A
tool call carries a JSON string, and there is no way to put a photograph in one —
see image_store for why routing the bytes through the model's context is not an
option either. So `build_tool()` wraps the agent in a tool that takes the image
*reference*, resolves the pixels itself, and hands the agent a proper multimodal
message. From the orchestrator's side it looks like every other specialist.

Two independent readings of the same photo meet here: the PlantVillage-trained
classifier, which is accurate on the ten tomato classes and blind to everything
else, and Claude's own reading of the image, which recognises when the photo is
not a tomato leaf at all. Neither alone is safe. The classifier will label a
chilli leaf as tomato late blight with 90% confidence, and the general model
guesses at the fine distinctions between the blights and spots the classifier was
trained for. The prompt below makes the agent hold both and say when they disagree.
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
TOOL_NAMES = ("leaf_disease_classify",)

ROLE = """\
You are the plant disease specialist in an advisory service for Indian farmers. A
photograph of the affected plant is attached to the message you are reading."""

DUTIES = """\
HOW TO WORK THROUGH A PHOTO.

First look at the photograph yourself and note what you actually see: which crop it
appears to be, which part of the plant, and what the damage looks like — spots and
their pattern, mould, curling, mottling, webbing, holes, wilting.

Then call leaf_disease_classify with the image reference you were given. It runs a
model trained on the ten PlantVillage tomato classes and returns the likeliest
classes with a confidence score, plus the treatment for the top one.

WEIGH THE TWO READINGS AGAINST EACH OTHER.

The classifier knows tomato leaves very well and nothing else at all. It has no way
to answer "this is not a tomato". Given a chilli leaf, a banana frond or a
photograph of a wall, it still returns a tomato disease, sometimes at high
confidence. Your own reading of the image is the only check on that.

- If the photo is a tomato leaf and you agree with the classifier, give that
  diagnosis and its treatment.
- If the photo is clearly not tomato, say so and ignore the classifier's label
  entirely. Describe what you can see, name the most likely problem only if the
  symptoms are unmistakable, and say that the trained model covers tomato only so
  this is a general reading. Never pass off a tomato label on another crop.
- If the photo is tomato but what you see contradicts the label, say the model
  suggests one thing and the photo looks like another, and give the more cautious
  of the two treatments.
- Follow the `how_to_present` instruction in the tool result. It tells you how far
  the confidence score lets you commit, and when the photo is too poor to call.

The tool result's `treatment` block is the only source for doses. Give the cultural
steps first — removing affected leaves, spacing, keeping water off the foliage —
because they cost nothing and a smallholder may not be able to buy a chemical this
week. Then give one chemical option with its rate, not the whole list: take the
first entry in `chemical_control`, which is the one chosen for the situation the
diagnosis describes. The later entries are alternatives for when the first cannot
be bought locally, and a farmer shown all three may buy and apply two of them.

Pass on the `note` when it warns against a wrong treatment, such as spraying a
fungicide at a virus or a mite.

Name the source as the leaf photo analysis, or the crop advisory's disease
reference. Never name the endpoint, the model or the dataset: "Agromemnon-leaf-
disease model" means nothing to a farmer and reads as a system leaking its
internals.

If the tool returns an error, tell the farmer plainly that you could not analyse
the photo. Do not diagnose from the image alone and do not name a dose.

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
    Accepting and discarding it keeps this module the same shape as the others.
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
