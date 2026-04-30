import os
from pathlib import Path

import moondream as md
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

IMAGE_PATH = Path("bases_screenshots") / "Egypt_147_base.jpg"
OUTPUT_PATH = Path("bases_screenshots") / "Egypt_147_base_detected.jpg"
DETECTION_OBJECT = "military facilities"


def draw_detection_boxes(image: Image.Image, detections: list[dict]) -> Image.Image:
    annotated_image = image.copy().convert("RGB")
    draw = ImageDraw.Draw(annotated_image)
    width, height = annotated_image.size

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()

    for index, detection in enumerate(detections, start=1):
        x_min = int(detection["x_min"] * width)
        y_min = int(detection["y_min"] * height)
        x_max = int(detection["x_max"] * width)
        y_max = int(detection["y_max"] * height)

        draw.rectangle((x_min, y_min, x_max, y_max), outline="red", width=4)
        label = f"{DETECTION_OBJECT} {index}"
        text_box = draw.textbbox((x_min, y_min), label, font=font)
        draw.rectangle(text_box, fill="red")
        draw.text((x_min, y_min), label, fill="white", font=font)

    return annotated_image


def main() -> None:
    load_dotenv()
    api_key = os.getenv("MOONDREAM_APY_KEY")

    if not api_key:
        raise ValueError("MOONDREAM_APY_KEY was not found in the .env file.")

    if not IMAGE_PATH.exists():
        raise FileNotFoundError(f"Image was not found: {IMAGE_PATH}")

    model = md.vl(api_key=api_key)

    with Image.open(IMAGE_PATH) as image:
        result = model.detect(image, DETECTION_OBJECT)
        detections = result["objects"]
        annotated_image = draw_detection_boxes(image, detections)

    annotated_image.save(OUTPUT_PATH)
    print(f"Detected {len(detections)} objects.")
    print(f"Saved annotated image: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
