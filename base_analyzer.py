import csv
import json
import os
import time
from io import BytesIO
from pathlib import Path

from LLM_military_bases_analysis import analyze_military_base
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


ROWS_TO_PROCCESS = 1
NUM_ANALYSIS_QUESTIONS = 2

ZOOM_IN_MULTIPLIER = 0.7
ZOOM_OUT_MULTIPLIER = 1.5
MOVE_LEFT_HEADING_DELTA = -30
MOVE_RIGHT_HEADING_DELTA = 30

CSV_PATH = Path("military_bases.csv")
SCREENSHOTS_DIR = Path("bases screenshots")
SELENIUM_DIR = Path(".selenium")
CHROME_PROFILE_DIR = SELENIUM_DIR / "chrome-profile"
CHROME_CACHE_DIR = SELENIUM_DIR / "chrome-cache"
SELENIUM_MANAGER_CACHE_DIR = SELENIUM_DIR / "manager-cache"

GOOGLE_EARTH_ALTITUDE = "10.04969521a"
GOOGLE_EARTH_DISTANCE = "1825.78590766d"
GOOGLE_EARTH_TILT = "30.00000016y"
GOOGLE_EARTH_HEADING = "-0h"
GOOGLE_EARTH_TIME = "0t"
GOOGLE_EARTH_ROLL = "0r"

PAGE_LOAD_WAIT_SECONDS = 12
UI_CLEANUP_WAIT_SECONDS = 4
SCREENSHOT_WIDTH_PIXELS = 1024
JPEG_QUALITY = 90

# Google Earth renders its controls inside the page. The crop removes the app
# toolbar at the top and the navigation/status controls at the bottom.
GOOGLE_EARTH_TOP_CROP_PIXELS = 155
GOOGLE_EARTH_BOTTOM_CROP_PIXELS = 225
GOOGLE_EARTH_LEFT_CROP_PIXELS = 0
GOOGLE_EARTH_RIGHT_CROP_PIXELS = 0


def build_google_earth_url(
    latitude: str,
    longitude: str,
    distance: str = GOOGLE_EARTH_DISTANCE,
    heading: str = GOOGLE_EARTH_HEADING,
) -> str:
    return (
        "https://earth.google.com/web/"
        f"@{latitude},{longitude},"
        f"{GOOGLE_EARTH_ALTITUDE},"
        f"{distance},"
        f"{GOOGLE_EARTH_TILT},"
        f"{heading},"
        f"{GOOGLE_EARTH_TIME},"
        f"{GOOGLE_EARTH_ROLL}"
    )


def create_driver() -> webdriver.Chrome:
    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    CHROME_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SELENIUM_MANAGER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SE_CACHE_PATH", str(SELENIUM_MANAGER_CACHE_DIR.resolve()))

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR.resolve()}")
    options.add_argument(f"--disk-cache-dir={CHROME_CACHE_DIR.resolve()}")

    # Headless mode is intentionally off so the browser is visible for debugging.
    return webdriver.Chrome(options=options)


def read_base_rows(
    csv_path: Path,
    rows_to_process: int = ROWS_TO_PROCCESS,
) -> list[dict[str, str]]:
    base_rows = []

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        for _ in range(rows_to_process):
            try:
                row = next(reader)
            except StopIteration:
                break

            base_rows.append(
                {
                    "country_name": (row.get("country") or"").strip(),
                    "latitude": (row.get("latitude") or "").strip(),
                    "longitude": (row.get("longitude") or "").strip(),
                }
            )

    return base_rows


def screenshot_base(
    driver: webdriver.Chrome,
    base_row: dict[str, str],
    distance: str = GOOGLE_EARTH_DISTANCE,
    heading: str = GOOGLE_EARTH_HEADING,
) -> Path:
    base_id = base_row["id"]
    latitude = base_row["latitude"]
    longitude = base_row["longitude"]
    earth_url = build_google_earth_url(latitude, longitude, distance, heading)
    screenshot_path = SCREENSHOTS_DIR / f"base_{base_id}.jpg"

    print(f"Opening base {base_id}: {earth_url}")
    driver.get(earth_url)
    time.sleep(PAGE_LOAD_WAIT_SECONDS)
    prepare_google_earth_for_screenshot(driver)
    save_resized_jpeg_screenshot(driver, screenshot_path)
    print(f"Saved screenshot: {screenshot_path}")

    return screenshot_path


def prepare_google_earth_for_screenshot(driver: webdriver.Chrome) -> None:
    dismiss_google_earth_popups(driver)
    time.sleep(1)


def dismiss_google_earth_popups(driver: webdriver.Chrome) -> None:
    popup_dismiss_x = 36
    popup_dismiss_y = 118

    try:
        dismiss_button = WebDriverWait(driver, UI_CLEANUP_WAIT_SECONDS).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//*[normalize-space()='Dismiss' or @aria-label='Dismiss']",
                )
            )
        )
        dismiss_button.click()
    except Exception:
        # Google Earth only shows the prompt sometimes.
        pass

    try:
        body = driver.find_element(By.TAG_NAME, "body")
        ActionChains(driver).move_to_element_with_offset(
            body,
            popup_dismiss_x,
            popup_dismiss_y,
        ).click().perform()
    except Exception:
        pass

    driver.execute_script(
        """
        const clickElementAtPoint = (x, y) => {
          const element = document.elementFromPoint(x, y);
          if (!element) {
            return;
          }
          const clickable = element.closest("button, a, [role='button']") || element;
          clickable.click();
        };

        clickElementAtPoint(36, 118);

        const findDismissButton = (root) => {
          const elements = root.querySelectorAll ? root.querySelectorAll("*") : [];
          for (const element of elements) {
          const text = (element.innerText || element.textContent || "").trim();
            const label = element.getAttribute("aria-label") || "";
            if (text === "Dismiss" || label === "Dismiss") {
              return element;
            }
            if (element.shadowRoot) {
              const match = findDismissButton(element.shadowRoot);
              if (match) {
                return match;
              }
            }
          }
          return null;
        };

        const dismissButton = findDismissButton(document);
        if (dismissButton) {
          dismissButton.click();
        }
        """
    )


def save_resized_jpeg_screenshot(
    driver: webdriver.Chrome,
    screenshot_path: Path,
) -> None:
    screenshot_png = driver.get_screenshot_as_png()

    with Image.open(BytesIO(screenshot_png)) as image:
        cropped_image = crop_google_earth_viewport(image)
        resize_ratio = SCREENSHOT_WIDTH_PIXELS / cropped_image.width
        resized_height = round(cropped_image.height * resize_ratio)
        resized_image = cropped_image.resize(
            (SCREENSHOT_WIDTH_PIXELS, resized_height),
            Image.Resampling.LANCZOS,
        ).convert("RGB")
        resized_image.save(screenshot_path, format="JPEG", quality=JPEG_QUALITY)


def crop_google_earth_viewport(image: Image.Image) -> Image.Image:
    left = GOOGLE_EARTH_LEFT_CROP_PIXELS
    top = GOOGLE_EARTH_TOP_CROP_PIXELS
    right = image.width - GOOGLE_EARTH_RIGHT_CROP_PIXELS
    bottom = image.height - GOOGLE_EARTH_BOTTOM_CROP_PIXELS

    if right <= left or bottom <= top:
        return image

    return image.crop((left, top, right, bottom))


def get_overall_analyzation(country_name, latitude, longitude) -> str:
    SCREENSHOTS_DIR.mkdir(exist_ok=True)

    distance = float(GOOGLE_EARTH_DISTANCE.rstrip("d"))
    heading = float(GOOGLE_EARTH_HEADING.rstrip("h"))
    history_of_analysts = ""
    history_records = []

    driver = create_driver()
    try:
        for analysis_index in range(NUM_ANALYSIS_QUESTIONS):
            screenshot_path = screenshot_base(
                driver,
                {
                    "id": f"{latitude}_{longitude}_{analysis_index + 1}",
                    "latitude": latitude,
                    "longitude": longitude,
                },
                f"{distance}d",
                f"{heading}h",
            )

            llm_response = analyze_military_base(
                country_name,
                analysis_index > 0,
                screenshot_path,
                history_of_analysts,
            )
            print(llm_response)

            llm_response_json = json.loads(llm_response)
            history_records.append(
                {
                    "findings": llm_response_json.get("findings", []),
                    "analysis": llm_response_json.get("analysis", ""),
                    "things_to_continue_analyzing": llm_response_json.get(
                        "things_to_continue_analyzing",
                        [],
                    ),
                }
            )
            history_of_analysts = json.dumps(history_records)

            action = llm_response_json.get("action")
            if not action or action == "finish":
                break

            if action == "zoom-in":
                distance *= ZOOM_IN_MULTIPLIER
            elif action == "zoom-out":
                distance *= ZOOM_OUT_MULTIPLIER
            elif action == "move-left":
                heading += MOVE_LEFT_HEADING_DELTA
            elif action == "move-right":
                heading += MOVE_RIGHT_HEADING_DELTA
            else:
                break
    finally:
        driver.quit()

    return history_of_analysts


def main() -> None:
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    base_rows = read_base_rows(CSV_PATH, ROWS_TO_PROCCESS)
    get_overall_analyzation(base_rows[0]["country_name"], base_rows[0]["latitude"], base_rows[0]["longitude"])
    


if __name__ == "__main__":
    main()
