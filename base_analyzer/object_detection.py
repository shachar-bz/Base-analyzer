import os
from functools import lru_cache
from pathlib import Path

import moondream as md
from dotenv import load_dotenv
from PIL import Image, ImageDraw


API_KEY_ENV_VAR = "MOONDREAM_API_KEY"
BOX_COLOR = "red"
BOX_WIDTH = 4


@lru_cache(maxsize=1)
def get_moondream_model():
    load_dotenv()
    api_key = os.getenv("MOONDREAM_API_KEY")

    if not api_key:
        raise ValueError(f"{API_KEY_ENV_VAR} was not found in the .env file.")

    return md.vl(api_key=api_key)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def normalized_box_to_pixels(
    detection: dict,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    x_min = int(clamp(float(detection["x_min"]), 0.0, 1.0) * image_width)
    y_min = int(clamp(float(detection["y_min"]), 0.0, 1.0) * image_height)
    x_max = int(clamp(float(detection["x_max"]), 0.0, 1.0) * image_width)
    y_max = int(clamp(float(detection["y_max"]), 0.0, 1.0) * image_height)

    return (
        min(x_min, x_max),
        min(y_min, y_max),
        max(x_min, x_max),
        max(y_min, y_max),
    )


def draw_detection_boxes(
    image: Image.Image,
    detections: list[dict],
) -> Image.Image:
    annotated_image = image.copy().convert("RGB")
    draw = ImageDraw.Draw(annotated_image)
    width, height = annotated_image.size

    for detection in detections:
        x_min, y_min, x_max, y_max = normalized_box_to_pixels(
            detection,
            width,
            height,
        )

        draw.rectangle((x_min, y_min, x_max, y_max), outline=BOX_COLOR, width=BOX_WIDTH)

    return annotated_image


def detect_objects_in_image(image_path: Path, object_name: str) -> tuple[Image.Image, int]:
    cleaned_object_name = object_name.strip()

    if not cleaned_object_name:
        raise ValueError("Object name is required.")

    if not image_path.exists():
        raise FileNotFoundError(f"Image was not found: {image_path}")

    model = get_moondream_model()

    with Image.open(image_path) as image:
        result = model.detect(image, cleaned_object_name)
        detections = result.get("objects", [])
        annotated_image = draw_detection_boxes(image, detections)

    return annotated_image, len(detections)
