import csv
import json
import os
import tempfile
import time
from io import BytesIO
from pathlib import Path

from base_analyzer.analyst import analyze_military_base, commander_analysis
from base_analyzer.base_store import (
    PROJECT_DIR,
    UNKNOWN_COUNTRY,
    AnalystReport,
    Base,
    BaseStore,
    CommanderSummary,
)
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


ROWS_TO_PROCCESS = 16
NUM_ANALYSIS_QUESTIONS = 8

ZOOM_IN_MULTIPLIER = 0.85
ZOOM_OUT_MULTIPLIER = 1.2
MOVE_LEFT_LONGITUDE_DELTA = -0.002
MOVE_RIGHT_LONGITUDE_DELTA = 0.002

CSV_PATH = PROJECT_DIR / "military_bases.csv"
SELENIUM_DIR = PROJECT_DIR / ".selenium"
CHROME_PROFILE_DIR = SELENIUM_DIR / "chrome-profile"
CHROME_CACHE_DIR = SELENIUM_DIR / "chrome-cache"
SELENIUM_MANAGER_CACHE_DIR = SELENIUM_DIR / "manager-cache"

GOOGLE_EARTH_ALTITUDE = "10.04969521a"
GOOGLE_EARTH_DISTANCE = "1650d"
GOOGLE_EARTH_TILT = "30.00000016y"
GOOGLE_EARTH_HEADING = "-0h"
GOOGLE_EARTH_TIME = "0t"
GOOGLE_EARTH_ROLL = "0r"

PAGE_LOAD_WAIT_SECONDS = 10
UI_CLEANUP_WAIT_SECONDS = 4
SCREENSHOT_WIDTH_PIXELS = 1024
JPEG_QUALITY = 90
GOOGLE_EARTH_BLOCK_RETRY_WAIT_SECONDS = 30
MAX_CONSECUTIVE_GOOGLE_EARTH_FAILURES = 2


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


def read_base_list(csv_path: Path, rows_to_process: int = ROWS_TO_PROCCESS) -> list[Base]:
    bases = []

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        for _ in range(rows_to_process):
            try:
                row = next(reader)
            except StopIteration:
                break

            bases.append(
                Base(
                    id=(row.get("id") or "").strip(),
                    country=(row.get("country") or "").strip() or UNKNOWN_COUNTRY,
                    latitude=(row.get("latitude") or "").strip(),
                    longitude=(row.get("longitude") or "").strip(),
                )
            )

    return bases


def screenshot_base(
    driver: webdriver.Chrome,
    base_row: dict[str, str],
    screenshot_path: Path,
    distance: str = GOOGLE_EARTH_DISTANCE,
    heading: str = GOOGLE_EARTH_HEADING,
) -> Path:
    base_id = base_row["id"]
    latitude = base_row["latitude"]
    longitude = base_row["longitude"]
    earth_url = build_google_earth_url(latitude, longitude, distance, heading)

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
        resize_ratio = SCREENSHOT_WIDTH_PIXELS / image.width
        resized_height = round(image.height * resize_ratio)
        resized_image = image.resize(
            (SCREENSHOT_WIDTH_PIXELS, resized_height),
            Image.Resampling.LANCZOS,
        ).convert("RGB")
        resized_image.save(screenshot_path, format="JPEG", quality=JPEG_QUALITY)


def get_overall_analyzation(country_name, base_id, latitude, longitude, saved_base_screenshot_path) -> str:
    saved_base_screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    distance = float(GOOGLE_EARTH_DISTANCE.rstrip("d"))
    current_longitude = float(longitude)
    heading = GOOGLE_EARTH_HEADING
    history_of_analysts = ""
    history_records = []

    driver = None
    consecutive_google_earth_failures = 0
    try:
        for analysis_index in range(NUM_ANALYSIS_QUESTIONS):
            temporary_screenshot_path = None
            if analysis_index == 0:
                screenshot_path = saved_base_screenshot_path
            else:
                temporary_screenshot = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".jpg",
                )
                temporary_screenshot_path = Path(temporary_screenshot.name)
                temporary_screenshot.close()
                screenshot_path = temporary_screenshot_path

            while True:
                try:
                    if driver is None:
                        driver = create_driver()

                    screenshot_path = screenshot_base(
                        driver,
                        {
                            "id": base_id,
                            "latitude": latitude,
                            "longitude": str(current_longitude),
                        },
                        screenshot_path,
                        f"{distance}d",
                        heading,
                    )
                    consecutive_google_earth_failures = 0
                    break
                except Exception as error:
                    consecutive_google_earth_failures += 1
                    print(
                        f"Failed opening Google Earth/Chrome for base {base_id} "
                        f"({country_name}), analysis {analysis_index + 1}: {error}"
                    )

                    if driver is not None:
                        try:
                            driver.quit()
                        except Exception:
                            pass
                        driver = None

                    if temporary_screenshot_path is not None:
                        temporary_screenshot_path.unlink(missing_ok=True)

                    print(
                        "Sleeping for "
                        f"{GOOGLE_EARTH_BLOCK_RETRY_WAIT_SECONDS} seconds."
                    )
                    time.sleep(GOOGLE_EARTH_BLOCK_RETRY_WAIT_SECONDS)

                    if (
                        consecutive_google_earth_failures
                        >= MAX_CONSECUTIVE_GOOGLE_EARTH_FAILURES
                    ):
                        print(
                            f"Failed to analyze base {base_id} ({country_name}) "
                            f"at analysis {analysis_index + 1}: {error}. "
                            "Got blocked twice, end program"
                        )
                        raise SystemExit(1)

            history_for_next_analyst = [
                {
                    "findings": history_record.get("findings", []),
                    "things_to_continue_analyzing": history_record.get(
                        "things_to_continue_analyzing",
                        [],
                    ),
                }
                for history_record in history_records
            ]
            history_of_previous_analysts = json.dumps(history_for_next_analyst)
            try:
                llm_response = analyze_military_base(
                    country_name,
                    analysis_index > 0,
                    screenshot_path,
                    history_of_previous_analysts,
                )
            finally:
                if temporary_screenshot_path is not None:
                    temporary_screenshot_path.unlink(missing_ok=True)

            llm_response_json = json.loads(llm_response)
            action = llm_response_json.get("action")
            print(f"Action for base {base_id}, analysis {analysis_index + 1}: {action}")
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

            if not action or action == "finish":
                break

            if action == "zoom-in":
                distance *= ZOOM_IN_MULTIPLIER
            elif action == "zoom-out":
                distance *= ZOOM_OUT_MULTIPLIER
            elif action == "move-left":
                current_longitude += MOVE_LEFT_LONGITUDE_DELTA
            elif action == "move-right":
                current_longitude += MOVE_RIGHT_LONGITUDE_DELTA
            else:
                break
    finally:
        if driver is not None:
            driver.quit()

    return history_of_analysts

def get_commander_analysis(history_of_analysts):
    commander_response = commander_analysis(history_of_analysts)
    return json.loads(commander_response)


def main() -> None:
    store = BaseStore()
    analyzed_bases = store.load()

    for base in read_base_list(CSV_PATH, ROWS_TO_PROCCESS):
        if base.id in analyzed_bases:
            print(f"Skipping base {base.id}; already exists in {store.data_path.name}.")
            continue

        history_of_analysts = get_overall_analyzation(
            base.country,
            base.id,
            base.latitude,
            base.longitude,
            store.screenshot_path(base),
        )
        base.analyst_reports = [
            AnalystReport.from_dict(record) for record in json.loads(history_of_analysts)
        ]
        base.commander_summary = CommanderSummary.from_dict(
            get_commander_analysis(history_of_analysts)
        )

        analyzed_bases[base.id] = base
        store.save(analyzed_bases)


if __name__ == "__main__":
    main()
