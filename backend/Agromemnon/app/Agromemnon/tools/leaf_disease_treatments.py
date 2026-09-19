"""Treatment reference for the tomato classes the leaf classifier can emit.

Why this file exists rather than letting the model write the cure from memory: the
shared guardrails forbid stating a quantity that did not come from a tool result,
and a spray dose is exactly the figure a farmer acts on without checking. A
hallucinated "3 ml per litre" reads identically to a correct one. So the classifier
tool returns the treatment alongside the diagnosis, and the model's job is to
select and translate, never to supply numbers.

Rates follow the state agricultural university / ICAR packages of practices for
tomato. They are the common label rates, not a substitute for the label: product
concentrations vary by brand, and `confirm_with` is returned on every record so the
answer can say so.

Keys must match the PlantVillage directory names exactly — scripts/plantvillage/
prepare_data.py trains on those names and the endpoint emits them verbatim.
"""

# Appended to every chemical recommendation. Kept in one place because a
# per-record copy would drift, and this is the sentence that keeps a farmer from
# mixing two products or ignoring the pre-harvest interval.
SPRAY_SAFETY = (
    "Spray in the cool part of the day, wet both leaf surfaces, and observe the "
    "pre-harvest interval printed on the product label before picking fruit. Do not "
    "tank-mix products unless the label allows it."
)

CONFIRM_WITH = (
    "Confirm the product and dose with your local Krishi Vigyan Kendra (KVK) or state "
    "agriculture department before spraying."
)

TREATMENTS = {
    "Tomato___Bacterial_spot": {
        "common_name": "Bacterial spot",
        "pathogen": "Xanthomonas spp. (bacterium)",
        "severity": "moderate",
        "what_you_see": (
            "Small dark water-soaked spots on leaves that dry to brown with a yellow halo; "
            "raised scabby spots on fruit. Worst in warm wet weather."
        ),
        "spreads_by": "Splashing rain and overhead irrigation, infected seed and seedlings, handling wet plants.",
        "cultural_control": [
            "Use certified disease-free seed and seedlings.",
            "Switch from overhead irrigation to drip or furrow so leaves stay dry.",
            "Do not work among the plants while the foliage is wet.",
            "Remove and destroy badly infected plants; rotate away from tomato, chilli and brinjal for 2 years.",
        ],
        "chemical_control": [
            "Copper oxychloride 50% WP at 3 g per litre of water, sprayed at 10-day intervals.",
            "Streptomycin sulphate at 100 ppm (1 g in 10 litres) tank-mixed with the copper spray where permitted.",
        ],
        "note": "Bacterial, not fungal — ordinary fungicides such as mancozeb will not control it.",
    },
    "Tomato___Early_blight": {
        "common_name": "Early blight",
        "pathogen": "Alternaria solani (fungus)",
        "severity": "moderate",
        "what_you_see": (
            "Brown spots with dark concentric rings, like a target, starting on the oldest "
            "lowest leaves and moving up. Leaves yellow and drop, exposing fruit to sunscald."
        ),
        "spreads_by": "Fungus surviving on crop debris and in soil; splashed up onto lower leaves by rain and irrigation.",
        "cultural_control": [
            "Pick off and destroy the affected lower leaves as soon as spots appear.",
            "Mulch around the base so soil does not splash onto the foliage.",
            "Stake the plants for airflow and space them wider.",
            "Keep nitrogen adequate — starved plants lose lower leaves fastest.",
        ],
        "chemical_control": [
            "Mancozeb 75% WP at 2 g per litre of water, every 10 to 12 days.",
            "Chlorothalonil 75% WP at 2 g per litre as an alternative protectant.",
            "Difenoconazole 25% EC at 0.5 ml per litre when spots are already spreading.",
        ],
        "note": "Alternate between two different chemical groups so the fungus does not build resistance.",
    },
    "Tomato___Late_blight": {
        "common_name": "Late blight",
        "pathogen": "Phytophthora infestans (oomycete)",
        "severity": "urgent",
        "what_you_see": (
            "Large greasy grey-green blotches on leaves that turn brown/black, often with white "
            "fuzzy growth on the underside in the morning; dark firm patches on fruit; stems blacken."
        ),
        "spreads_by": "Airborne spores in cool (10-24 C) humid or rainy weather; can destroy a field in under a week.",
        "cultural_control": [
            "Act the same day — this one moves faster than any other tomato disease.",
            "Remove and burn or bury affected plants; do not leave them on the field bund.",
            "Improve drainage and avoid evening irrigation.",
            "Destroy volunteer tomato and potato plants nearby, which carry the pathogen over.",
        ],
        "chemical_control": [
            "Cymoxanil 8% + Mancozeb 64% WP at 3 g per litre of water, as the curative spray.",
            "Metalaxyl 8% + Mancozeb 64% WP at 2.5 g per litre, repeated after 10 days.",
            "Mancozeb 75% WP at 2.5 g per litre as a protectant on the remaining healthy plants.",
        ],
        "note": "Treat the whole field, not only the visibly affected plants — spores have already travelled.",
    },
    "Tomato___Leaf_Mold": {
        "common_name": "Leaf mould",
        "pathogen": "Passalora fulva (fungus)",
        "severity": "moderate",
        "what_you_see": (
            "Pale yellow patches on the upper leaf surface with olive-green to brown velvety mould "
            "directly beneath them. Almost always starts on the lower leaves."
        ),
        "spreads_by": "High humidity above 85%, poor ventilation. Common in polyhouses and shade nets.",
        "cultural_control": [
            "Bring the humidity down — open vents, increase spacing, prune lower leaves.",
            "Water the soil, never the canopy, and do it early enough that leaves dry before night.",
            "Remove affected leaves and destroy crop residue after harvest.",
            "Use a resistant variety for the next polyhouse crop.",
        ],
        "chemical_control": [
            "Chlorothalonil 75% WP at 2 g per litre of water.",
            "Mancozeb 75% WP at 2 g per litre.",
            "Difenoconazole 25% EC at 0.5 ml per litre for established infections.",
        ],
        "note": "Ventilation does more here than any spray; chemical control alone rarely clears it.",
    },
    "Tomato___Septoria_leaf_spot": {
        "common_name": "Septoria leaf spot",
        "pathogen": "Septoria lycopersici (fungus)",
        "severity": "moderate",
        "what_you_see": (
            "Many small round spots with grey-white centres and dark brown edges, with tiny black "
            "dots visible in the centre. Starts on the lowest leaves shortly after fruit set."
        ),
        "spreads_by": "Splashed water from soil and infected debris; favoured by warm wet weather.",
        "cultural_control": [
            "Strip and destroy the lowest infected leaves early, before the spots reach mid-canopy.",
            "Mulch to stop soil splash and stake for airflow.",
            "Clear all tomato debris after harvest; the fungus overwinters on it.",
            "Rotate out of tomato for at least 2 years; control nightshade weeds on the bund.",
        ],
        "chemical_control": [
            "Mancozeb 75% WP at 2 g per litre of water, every 7 to 10 days in wet weather.",
            "Chlorothalonil 75% WP at 2 g per litre.",
        ],
        "note": "Spots stay small and numerous — unlike early blight, there are no concentric rings.",
    },
    "Tomato___Spider_mites Two-spotted_spider_mite": {
        "common_name": "Two-spotted spider mite",
        "pathogen": "Tetranychus urticae (mite — a pest, not a disease)",
        "severity": "moderate",
        "what_you_see": (
            "Fine pale speckling or stippling over the leaf, leaves turning bronze and dry, and fine "
            "webbing on the undersides and shoot tips. Look under the leaf with a lens for moving dots."
        ),
        "spreads_by": "Hot dry dusty weather; carried on clothing, tools and wind. Populations double in days above 30 C.",
        "cultural_control": [
            "Hose the undersides of leaves with plain water to knock mites off and raise humidity.",
            "Remove and destroy the worst-affected leaves; control dust on field roads.",
            "Avoid excess nitrogen, which makes foliage more attractive to mites.",
            "Protect natural predators — predatory mites and ladybird beetles suppress low populations.",
        ],
        "chemical_control": [
            "Wettable sulphur 80% WP at 3 g per litre of water for a light infestation.",
            "Spiromesifen 22.9% SC at 1 ml per litre of water.",
            "Propargite 57% EC at 2 ml per litre, or Abamectin 1.9% EC at 0.5 ml per litre.",
            "Neem oil at 5 ml per litre with a wetting agent, for organic management.",
        ],
        "note": (
            "Use a miticide, not a fungicide. Spray the leaf undersides — that is where the mites live, "
            "and a top-only spray does nothing. Rotate the chemical group every spray; mites develop "
            "resistance faster than almost any other pest."
        ),
    },
    "Tomato___Target_Spot": {
        "common_name": "Target spot",
        "pathogen": "Corynespora cassiicola (fungus)",
        "severity": "moderate",
        "what_you_see": (
            "Small brown spots that enlarge into light brown lesions with faint concentric rings and a "
            "yellow margin, on leaves, stems and fruit. Sunken circular spots on the fruit."
        ),
        "spreads_by": "Warm humid conditions and extended leaf wetness; spores carried on wind and splash.",
        "cultural_control": [
            "Space and stake plants so the canopy dries quickly.",
            "Remove affected leaves and destroy crop residue.",
            "Avoid overhead irrigation; rotate away from tomato and other hosts.",
        ],
        "chemical_control": [
            "Mancozeb 75% WP at 2 g per litre of water.",
            "Chlorothalonil 75% WP at 2 g per litre.",
            "Azoxystrobin 23% SC at 1 ml per litre when the fruit is being affected.",
        ],
        "note": "Easily mistaken for early blight; target spot also marks the fruit, early blight mostly does not.",
    },
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": {
        "common_name": "Tomato yellow leaf curl virus (TYLCV)",
        "pathogen": "Begomovirus, spread by whitefly",
        "severity": "urgent",
        "what_you_see": (
            "Leaves small, cupped upward and curled at the margins, yellowing between the veins, plant "
            "stunted and bushy. Flowers drop and almost no fruit sets after infection."
        ),
        "spreads_by": "Whitefly (Bemisia tabaci) only — not by touch, tools or soil.",
        "cultural_control": [
            "There is no cure for an infected plant. Pull it out and destroy it so it stops being a source.",
            "Control the whitefly, which is the only thing that spreads it.",
            "Put up yellow sticky traps at 10 to 12 per acre and check them weekly.",
            "Grow a 2-row maize or bajra barrier around the plot and use a 40-mesh net over the nursery.",
            "For the next crop choose a resistant variety such as Arka Rakshak or Arka Samrat.",
        ],
        "chemical_control": [
            "Target the whitefly, not the virus: Imidacloprid 17.8% SL at 0.3 ml per litre of water.",
            "Diafenthiuron 50% WP at 1 g per litre, alternated with the above to slow resistance.",
            "Neem oil at 5 ml per litre as a repellent in low-pressure situations.",
        ],
        "note": "No spray cures an infected plant. Every rupee here should go on whitefly control and roguing.",
    },
    "Tomato___Tomato_mosaic_virus": {
        "common_name": "Tomato mosaic virus (ToMV)",
        "pathogen": "Tobamovirus",
        "severity": "urgent",
        "what_you_see": (
            "Light and dark green mottling or mosaic on the leaves, sometimes fern-like narrowing of the "
            "leaflets, stunted growth and mottled uneven ripening in the fruit."
        ),
        "spreads_by": (
            "Sap on hands, clothing, tools and stakes, and on infected seed. Extremely stable — survives "
            "on dry debris for years. Not spread by insects."
        ),
        "cultural_control": [
            "There is no cure. Rogue out affected plants and destroy them away from the field.",
            "Wash hands with soap and dip tools in 1% sodium hypochlorite or trisodium phosphate between plants.",
            "Do not use tobacco or handle bidis while working in the crop — the virus is carried in tobacco.",
            "Treat seed with 10% trisodium phosphate for 15 minutes, then rinse, before the next sowing.",
            "Destroy all crop residue and stakes, or disinfect stakes before reuse.",
        ],
        "chemical_control": [
            "No chemical controls the virus. Do not spend on fungicides or insecticides for this.",
        ],
        "note": "Sanitation is the entire treatment. A single unwashed hand can carry it down a whole row.",
    },
    "Tomato___healthy": {
        "common_name": "Healthy",
        "pathogen": None,
        "severity": "none",
        "what_you_see": "Uniform green leaf with no spots, mottling, curling, mould or webbing.",
        "spreads_by": None,
        "cultural_control": [
            "No treatment needed. Keep up routine scouting of the lower leaves twice a week.",
            "Keep irrigation off the foliage and maintain spacing to prevent the common leaf diseases.",
        ],
        "chemical_control": [],
        "note": "No disease detected in this photo. That covers this leaf only, not the whole field.",
    },
}


def for_label(label: str) -> dict | None:
    """Return the treatment record for a classifier label, or None if unmapped."""
    record = TREATMENTS.get(label)
    if record is None:
        return None

    record = dict(record)
    record["confirm_with"] = CONFIRM_WITH
    if record["chemical_control"]:
        record["spray_safety"] = SPRAY_SAFETY
    return record


def display_name(label: str) -> str:
    """Farmer-facing name for a label, falling back to a tidied directory name."""
    record = TREATMENTS.get(label)
    if record:
        return record["common_name"]
    return label.replace("Tomato___", "").replace("_", " ").strip()
