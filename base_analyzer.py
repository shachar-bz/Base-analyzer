import csv
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


ROWS_TO_PROCCESS = 5
CSV_PATH = Path("military_bases.csv")
SCREENSHOTS_DIR = Path("bases screenshots")

GOOGLE_EARTH_ALTITUDE = "10.04969521a"
GOOGLE_EARTH_DISTANCE = "1825.78590766d"
GOOGLE_EARTH_TILT = "30.00000016y"
GOOGLE_EARTH_HEADING = "-0h"
GOOGLE_EARTH_TIME = "0t"
GOOGLE_EARTH_ROLL = "0r"

PAGE_LOAD_WAIT_SECONDS = 12


def build_google_earth_url(latitude: str, longitude: str) -> str:
    return (
        "https://earth.google.com/web/"
        f"@{latitude},{longitude},"
        f"{GOOGLE_EARTH_ALTITUDE},"
        f"{GOOGLE_EARTH_DISTANCE},"
        f"{GOOGLE_EARTH_TILT},"
        f"{GOOGLE_EARTH_HEADING},"
        f"{GOOGLE_EARTH_TIME},"
        f"{GOOGLE_EARTH_ROLL}"
    )


def create_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")

    # Headless mode is intentionally off so the browser is visible for debugging.
    return webdriver.Chrome(options=options)


def read_base_rows(csv_path: Path, rows_to_process: int) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))[:rows_to_process]


def screenshot_base(driver: webdriver.Chrome, base_row: dict[str, str]) -> Path:
    base_id = base_row["id"]
    latitude = base_row["latitude"]
    longitude = base_row["longitude"]
    earth_url = build_google_earth_url(latitude, longitude)
    screenshot_path = SCREENSHOTS_DIR / f"base_{base_id}.png"

    print(f"Opening base {base_id}: {earth_url}")
    driver.get(earth_url)
    time.sleep(PAGE_LOAD_WAIT_SECONDS)
    driver.save_screenshot(str(screenshot_path))
    print(f"Saved screenshot: {screenshot_path}")

    return screenshot_path


def main() -> None:
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    base_rows = read_base_rows(CSV_PATH, ROWS_TO_PROCCESS)

    if not base_rows:
        print(f"No rows found in {CSV_PATH}")
        return

    driver = create_driver()
    try:
        for base_row in base_rows:
            screenshot_base(driver, base_row)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
