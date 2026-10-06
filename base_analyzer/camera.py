"""Camera adapter: screenshots of Google Earth in a visible Chrome window."""

import os
import time
from io import BytesIO

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from base_analyzer.analysis_loop import View
from base_analyzer.base_store import PROJECT_DIR


SELENIUM_DIR = PROJECT_DIR / ".selenium"
CHROME_PROFILE_DIR = SELENIUM_DIR / "chrome-profile"
CHROME_CACHE_DIR = SELENIUM_DIR / "chrome-cache"
SELENIUM_MANAGER_CACHE_DIR = SELENIUM_DIR / "manager-cache"

GOOGLE_EARTH_ALTITUDE = "10.04969521a"
GOOGLE_EARTH_TILT = "30.00000016y"
GOOGLE_EARTH_HEADING = "-0h"
GOOGLE_EARTH_TIME = "0t"
GOOGLE_EARTH_ROLL = "0r"

PAGE_LOAD_WAIT_SECONDS = 10
UI_CLEANUP_WAIT_SECONDS = 4
SCREENSHOT_WIDTH_PIXELS = 1024
JPEG_QUALITY = 90
RETRY_WAIT_SECONDS = 30
MAX_CONSECUTIVE_FAILURES = 2

# Where Google Earth's welcome popup has its close control.
POPUP_DISMISS_X = 36
POPUP_DISMISS_Y = 118


class GoogleEarthBlocked(Exception):
    """Google Earth failed to load several times in a row; it has probably blocked us."""


def google_earth_url(view: View) -> str:
    return (
        "https://earth.google.com/web/"
        f"@{view.latitude},{view.longitude},"
        f"{GOOGLE_EARTH_ALTITUDE},"
        f"{view.distance_meters}d,"
        f"{GOOGLE_EARTH_TILT},"
        f"{GOOGLE_EARTH_HEADING},"
        f"{GOOGLE_EARTH_TIME},"
        f"{GOOGLE_EARTH_ROLL}"
    )


class GoogleEarthCamera:
    """Opens Chrome on first capture and quits it on close()."""

    def __init__(self) -> None:
        self._driver: webdriver.Chrome | None = None
        self._consecutive_failures = 0

    def __enter__(self) -> "GoogleEarthCamera":
        return self

    def __exit__(self, *exception_info) -> None:
        self.close()

    def close(self) -> None:
        if self._driver is None:
            return

        try:
            self._driver.quit()
        except Exception:
            pass
        self._driver = None

    def capture(self, view: View) -> bytes:
        while True:
            try:
                image = self._capture_once(view)
                self._consecutive_failures = 0
                return image
            except Exception as error:
                self._consecutive_failures += 1
                print(f"Failed opening Google Earth/Chrome: {error}")
                self.close()

                if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    raise GoogleEarthBlocked(
                        f"Google Earth failed {self._consecutive_failures} times in a row: {error}"
                    ) from error

                print(f"Sleeping for {RETRY_WAIT_SECONDS} seconds.")
                time.sleep(RETRY_WAIT_SECONDS)

    def _capture_once(self, view: View) -> bytes:
        if self._driver is None:
            self._driver = create_driver()

        url = google_earth_url(view)
        print(f"Opening {url}")
        self._driver.get(url)
        time.sleep(PAGE_LOAD_WAIT_SECONDS)
        dismiss_popups(self._driver)
        time.sleep(1)

        return resized_jpeg(self._driver.get_screenshot_as_png())


def create_driver() -> webdriver.Chrome:
    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    CHROME_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SELENIUM_MANAGER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SE_CACHE_PATH", str(SELENIUM_MANAGER_CACHE_DIR))

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    options.add_argument(f"--disk-cache-dir={CHROME_CACHE_DIR}")

    # Headless mode is intentionally off so the browser is visible for debugging.
    return webdriver.Chrome(options=options)


def dismiss_popups(driver: webdriver.Chrome) -> None:
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
            POPUP_DISMISS_X,
            POPUP_DISMISS_Y,
        ).click().perform()
    except Exception:
        pass

    driver.execute_script(
        """
        const [dismissX, dismissY] = arguments;

        const clickElementAtPoint = (x, y) => {
          const element = document.elementFromPoint(x, y);
          if (!element) {
            return;
          }
          const clickable = element.closest("button, a, [role='button']") || element;
          clickable.click();
        };

        clickElementAtPoint(dismissX, dismissY);

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
        """,
        POPUP_DISMISS_X,
        POPUP_DISMISS_Y,
    )


def resized_jpeg(screenshot_png: bytes) -> bytes:
    with Image.open(BytesIO(screenshot_png)) as image:
        resize_ratio = SCREENSHOT_WIDTH_PIXELS / image.width
        resized_height = round(image.height * resize_ratio)
        resized_image = image.resize(
            (SCREENSHOT_WIDTH_PIXELS, resized_height),
            Image.Resampling.LANCZOS,
        ).convert("RGB")

    jpeg = BytesIO()
    resized_image.save(jpeg, format="JPEG", quality=JPEG_QUALITY)
    return jpeg.getvalue()
