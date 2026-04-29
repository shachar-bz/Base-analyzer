import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


SCREENSHOTS_DIR = Path("bases screenshots")
MODEL_NAME = "gpt-5.4-nano"
PROMPT_TEMPLATE = """You are an expert satellite imagery analyst working for the US Army. The provided image shows a military base or facility operated by the armed forces of {country_name}.

CRITICAL INSTRUCTION: Your entire response must consist of nothing but a single valid JSON object. The output must start with the character {{ and contain only raw, parseable JSON. Do not include any other text, explanations, markdown, code blocks, apologies, or backticks before or after it.

Be direct, concise, and analytical.
- You may use phrases like "high probability", "likely", or "appears to".
- Do not include disclaimers about limitations or inability to confirm.
- Do not explain what you cannot see.
- Do not mention image quality or resolution.
- Do not use markdown symbols like * or #.
- Do not write long paragraphs.

Field Requirements:

"findings": Array of strings. Focus on identifying all man-made structures, military equipment, weapon systems, vehicles, aircraft, radar, launchers, bunkers, infrastructure, and activity. Be as specific as the resolution allows.
"analysis": String. Provide a detailed, professional assessment of the findings, their strategic/tactical significance and capabilities.
"things_to_continue_analyzing": Array of strings. List specific objects, areas, ambiguities, or questions that require additional imagery - there is no need to explain why we want additional imagery.
"action": String. Must be exactly one of: "zoom-in", "zoom-out", "move-left", "move-right", or "finish".
"zoom-in": zoom in the image in order to analysis something or identify in a better way/ more certinty.
"zoom-out": if the view is too narrow and you need broader context or scale of the facility/surrounding area.
"move-left" or "move-right": if militarily significant features appear cut off at the edge of the frame.
"finish": If you have high-confidence understanding of the facility's layout, primary capabilities, and equipment.

here there is an example of the exact structure you need to respond with
{{
  "findings": [],
  "analysis": "",
  "things_to_continue_analyzing": [],
  "action": "finish"
}}"""

HISTORY_PROMPT_TEMPLATE = "Here is the analysis of previous analysts about this area and their recommendations. You can use this data but dont use it as fact, think for yourself: {history_of_analysis}"


load_dotenv()
API_KEY = os.getenv("OPENAI_APY_KEY")


def encode_jpg_image_as_data_url(image_path: Path) -> str:
    with image_path.open("rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded_image}"


def analyze_military_base(country_name: str, is_using_history_prompt: bool, base_image: Path, history_of_analysis: str = "",) -> str:
    if not API_KEY:
        raise ValueError("The API key was not found in the .env file.")

    client = OpenAI(api_key=API_KEY)
    prompt = PROMPT_TEMPLATE.format(country_name=country_name)

    if is_using_history_prompt:
        history_prompt = HISTORY_PROMPT_TEMPLATE.format(history_of_analysis=history_of_analysis,)
        prompt = f"{prompt}\n\n{history_prompt}"

    response = client.responses.create(
        model=MODEL_NAME,
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



def main() -> None:
    country_name = "Egypt"

    if not country_name:
        print("Country name is required.")
        return

    image_paths = [
        image_path
        for image_path in SCREENSHOTS_DIR.iterdir()
        if image_path.is_file() and image_path.suffix.lower() == ".jpg"
    ]

    if not image_paths:
        print(f"No images found in '{SCREENSHOTS_DIR}'.")
        return

    print(analyze_military_base(country_name, False, image_paths[0]))


if __name__ == "__main__":
    main()
