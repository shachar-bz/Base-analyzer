import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


SCREENSHOTS_DIR = Path("bases screenshots")
MODEL_NAME = "gpt-5.4-nano"
PROMPT_TEMPLATE = """You are a military imagery analyst working for US intelligence.

Assume the site is military and interpret all observations accordingly.
We got intel that this area is a base/facility of the military of {country_name}.

Your task is to analyze the provided satellite image and identify structures, patterns, and objects that support military usage.

Rules:
- Be direct, concise, and analytical.
- You may use phrases like "high probability", "likely", or "appears to".
- Do not include disclaimers about limitations or inability to confirm.
- Do not explain what you cannot see.
- Do not mention image quality or resolution.
- Do not use markdown symbols like * or #.
- Do not write long paragraphs.

Output format:

1. Identified objects and structures
For each item:
- Object name
- Visual observation (what is seen)
- Likely military function
- Why it supports military usage

2. Overall assessment
- 2-4 sentences summarizing the role of the site (e.g., logistics, storage, defense, training)
- Use confident but not absolute language

Focus on:
- storage infrastructure (fuel tanks, depots, containers)
- defensive layouts (perimeter, segmentation, controlled access)
- logistics and movement (roads, staging areas, vehicle paths)
- spatial organization typical of military bases

Do not include any additional explanations outside this structure."""

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")


def encode_jpg_image_as_data_url(image_path: Path) -> str:
    with image_path.open("rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded_image}"


def analyze_military_base_screenshots(country_name: str) -> None:
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY was not found in the .env file.")

    client = OpenAI(api_key=API_KEY)

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

        response = client.responses.create(
            model=MODEL_NAME,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": encode_jpg_image_as_data_url(image_path),
                        },
                    ],
                }
            ],
        )

        print(response.output_text)


def main() -> None:
    country_name = input("Enter country name: ").strip()

    if not country_name:
        print("Country name is required.")
        return

    analyze_military_base_screenshots(country_name)


if __name__ == "__main__":
    main()
