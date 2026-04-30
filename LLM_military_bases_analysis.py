import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


ANALYSTS_MODEL_NAME = "gpt-5-nano"
COMMANDER_MODEL_NAME = "gpt-5.4-nano"

ANALYSTS_PROMPT_TEMPLATE = """You are an expert in understanding satellite imagery and you work for the US army.
We got intel that this area is a base/facility of the military of {country_name}.
Analyze this image and respond ONLY with a JSON object containing the following keys:
1. 'findings': A list of findings that you think are important for the US army to know, including
all man-made structures, military equipment, and infrastructure make sure to start each finding in a new line.
2. 'analysis': A detailed analysis of your findings make sure to start each finding in a new line.
3. 'things_to_continue_analyzing': A list of things that you think are important to continue
analyzing in further images make sure to start each thing in a new line.
4. 'action': One of ['zoom-in', 'zoom-out', 'move-left', 'move-right', 'finish'] based on what
would help you analyze the image or area better.
- Choose 'zoom-in' if you need to zoom in the image
- Choose 'zoom-out' if you need more context of the surrounding area or if you are zoomedin too much
- Choose 'move-left' or 'move-right' if you suspect there are important features just outside the current view
- Choose 'finish' if you have a complete understanding of the location Choose 'finish' if you think you have enough information about the base.
Respond ONLY with valid JSON. Do not include explanations or extra text.
"""

ANALYSTS_PROMPT_TEMPLATE_WITH_HISTORY = """Here is the analysis of previous analysts about this area and their recommendations on what else is needed to investigate, You can use this data but dont use it as fact, think for yourself:{history_of_analysts}
You are an expert in understanding satellite imagery and you work for the US army.
We got intel that this area is a base/facility of the military of {country_name}.
Analyze this image and respond ONLY with a JSON object containing the following keys:
1. 'findings': A list of findings that you think are important for the US army to know, including
all man-made structures, military equipment, and infrastructure make sure to start each finding in a new line.
2. 'analysis': A detailed list analysis of your findings make sure to start each finding in a new line.
3. 'things_to_continue_analyzing': A list of things that you think are important to continue
analyzing in further images make sure to start each thing in a new line.
4. 'action': One of ['zoom-in', 'zoom-out', 'move-left', 'move-right', 'finish'] based on what
would help you analyze the image or area better.
- Choose 'zoom-in' if you need to zoom in the image
- Choose 'zoom-out' if you need more context of the surrounding area or if you are zoomedin too much
- Choose 'move-left' or 'move-right' if you suspect there are important features just outside the current view
- Choose 'finish' if you have a complete understanding of the location Choose 'finish' if you think you have enough information about the base. Choose 'finish' if you think you have enough information about the base.
Respond ONLY with valid JSON. Do not include explanations or extra text.
"""

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

    if is_using_history_prompt:
        prompt = ANALYSTS_PROMPT_TEMPLATE_WITH_HISTORY.format(country_name=country_name, history_of_analysts=history_of_analysts)

    else:
        prompt = ANALYSTS_PROMPT_TEMPLATE.format(country_name=country_name)

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
