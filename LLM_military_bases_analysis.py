import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI



SCREENSHOTS_DIR = Path("bases screenshots")
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

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash"


def encode_jpg_image_as_data_url(image_path: Path) -> str:
    with image_path.open("rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded_image}"


def analyze_military_base_screenshots(country_name: str) -> None:
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY was not found in the .env file.")

    client = OpenAI(
        api_key=API_KEY,
         base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    image_paths = [
        image_path
        for image_path in SCREENSHOTS_DIR.iterdir()
        if image_path.is_file() and image_path.suffix.lower() == ".jpg"
    ]

    if not image_paths:
        print(f"No images found in '{SCREENSHOTS_DIR}'.")
        return

    prompt = PROMPT_TEMPLATE.format(country_name=country_name)

    for image_path in image_paths:
        print(f"\nAnalyzing {image_path}...")

        response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": encode_jpg_image_as_data_url(image_path),
                    },
                },
            ],
        }
    ],
    )

    print(response.choices[0].message.content)



def main() -> None:
    country_name = "Egypt"

    if not country_name:
        print("Country name is required.")
        return

    analyze_military_base_screenshots(country_name)


if __name__ == "__main__":
    main()
