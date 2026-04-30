import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


SCREENSHOTS_DIR = Path("bases screenshots")
ANALYSTS_MODEL_NAME = "gpt-5-nano"
COMMANDER_MODEL_NAME = "gpt-5.4-nano"

ANALYSTS_PROMPT_TEMPLATE = """You are an expert satellite imagery analyst working for the US Army. The provided image shows a military base or facility operated by the armed forces of {country_name}.

CRITICAL INSTRUCTION: Your entire response must consist of nothing but a single valid JSON object. The output must start with the character {{ and contain only raw, parseable JSON. Do not include any other text, explanations, markdown, code blocks, apologies, or backticks before or after it.

Be direct, concise, and analytical.
- You may use phrases like "high probability", "likely", or "appears to".
- Do not include disclaimers about limitations or inability to confirm.
- Do not explain what you cannot see.
- Do not mention image quality or resolution.
- Do not use markdown symbols.
- Do not write long paragraphs.

Field Requirements:

"findings": Array of strings. Focus on identifying all man-made structures, military equipment, weapon systems, vehicles, aircraft, radar, launchers, bunkers, infrastructure, and activity.
"analysis": Array of strings. Provide a detailed, professional assessment for each of the findings, elaborate on their strategic/tactical significance and capabilities.
"things_to_continue_analyzing": Array of strings. List specific objects, areas, or ambiguities that require additional imagery - there is no need to explain why we want additional imagery.
"action": String. Must be exactly one of: "zoom-in", "zoom-out", "move-left", "move-right", or "finish".
"zoom-in": zoom in the image in order to analysis something in a better way.
"zoom-out": if the view is too narrow.
"move-left" or "move-right": if militarily significant features appear cut off at the edge of the frame.
"finish": If you have high-confidence understanding of the facility's layout, primary capabilities, and equipment.

here there is an example of the exact structure you need to respond with
{{
  "findings": [],
  "analysis": [],
  "things_to_continue_analyzing": [],
  "action": "finish"
}}"""

HISTORY_ANALYSTS_PROMPT_TEMPLATE = "Here is the analysis of previous analysts about this area and their recommendations. You can use this data but dont use it as fact, think for yourself: {history_of_analysts}"

COMMANDER_PROMPT_TEMPLATE = """You are the commander of a team of imagery analysts.
You are reviewing multiple analyst reports about the same suspected military base or facility. Each report was written by a different analyst and may contain correct observations, uncertainty, or speculation.
Your job is to compare all analyst reports, identify what is strongly supported, separate facts from guesses, assign certainty levels, and produce one final commander-level conclusion.
Use the analyst reports as evidence, but do not blindly trust them. Think independently and avoid overclaiming.
Return only one valid JSON object. Do not include markdown, explanations, code blocks, backticks, or any text before or after the JSON.
Your response must use exactly this structure:

{{
  "summary": "Overall explanation of what the site most likely is, what it appears to contain, and its likely purpose. Mention uncertainty where needed.",
  "supported_observations": [
    "Observation with certainty level, for example: High confidence: The site includes a secured perimeter compound.",
    "Medium confidence: The site appears to contain internal roads and organized access routes.",
    "Low confidence: Some structures may be storage pads or equipment positions, but this is not confirmed."
  ],
  "recommendations": [
    "Specific next step for further imagery analysis, such as zooming into unclear structures, checking nearby roads, confirming vehicle types, or examining possible antennas/bunkers."
  ]
}}

Rules:
- Focus on consensus between analysts.
- Mark each supported observation with a certainty level: High confidence, Medium confidence, or Low confidence.
- Do not treat speculation as fact.
- Do not invent details that were not mentioned or visible.
- Do not include operational or attack recommendations.
- Recommendations should only describe what should be investigated further in imagery.
- Keep the answer professional, concise, and analytical.

Analyst reports:
{history_of_analysts}
"""

load_dotenv()
API_KEY = os.getenv("OPENAI_APY_KEY")


def encode_jpg_image_as_data_url(image_path: Path) -> str:
    with image_path.open("rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded_image}"


def analyze_military_base(country_name: str, is_using_history_prompt: bool, base_image: Path, history_of_analysts: str = "",) -> str:
    if not API_KEY:
        raise ValueError("The API key was not found in the .env file.")

    client = OpenAI(api_key=API_KEY)
    prompt = ANALYSTS_PROMPT_TEMPLATE.format(country_name=country_name)

    if is_using_history_prompt:
        history_prompt = HISTORY_ANALYSTS_PROMPT_TEMPLATE.format(history_of_analysts=history_of_analysts,)
        prompt = f"{prompt}\n\n{history_prompt}"

    response = client.responses.create(
        model=ANALYSTS_MODEL_NAME,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": encode_jpg_image_as_data_url(base_image),
                    },
                ],
            }
        ],
    )

    return response.output_text


def commander_analysis(history_of_analysts: str) -> str:
    if not API_KEY:
        raise ValueError("The API key was not found in the .env file.")

    client = OpenAI(api_key=API_KEY)
    prompt = COMMANDER_PROMPT_TEMPLATE.format(history_of_analysts=history_of_analysts)

    response = client.responses.create(
        model=COMMANDER_MODEL_NAME,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                ],
            }
        ],
    )

    return response.output_text
