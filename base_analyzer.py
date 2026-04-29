import csv
import os
import time
from io import BytesIO
from pathlib import Path

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


ROWS_TO_PROCCESS = 1
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


def read_base_rows(csv_path: Path, rows_to_process: int) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))[:rows_to_process]


def screenshot_base(driver: webdriver.Chrome, base_row: dict[str, str]) -> Path:
    base_id = base_row["id"]
    latitude = base_row["latitude"]
    longitude = base_row["longitude"]
    earth_url = build_google_earth_url(latitude, longitude)
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
