"""The Analysis loop: analysts take turns looking at a Base through a Camera.

Each analyst gets a fresh screenshot plus the earlier reports, writes an
AnalystReport and picks the next camera action. The loop only knows the
Camera and Analyst interfaces; camera.py and analyst.py hold the real
adapters, and the tests use fakes.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from base_analyzer.base_store import AnalystReport, Base


MAX_ANALYSTS = 8
ACTIONS = ("zoom-in", "zoom-out", "move-left", "move-right", "finish")

START_DISTANCE_METERS = 1650.0
ZOOM_IN_MULTIPLIER = 0.85
ZOOM_OUT_MULTIPLIER = 1.2
MOVE_LONGITUDE_DELTA = 0.002


@dataclass(frozen=True)
class View:
    """Where the camera looks: a point, and how far from it."""

    latitude: float
    longitude: float
    distance_meters: float = START_DISTANCE_METERS

    def after(self, action: str) -> "View":
        if action == "zoom-in":
            return replace(self, distance_meters=self.distance_meters * ZOOM_IN_MULTIPLIER)
        if action == "zoom-out":
            return replace(self, distance_meters=self.distance_meters * ZOOM_OUT_MULTIPLIER)
        if action == "move-left":
            return replace(self, longitude=self.longitude - MOVE_LONGITUDE_DELTA)
        if action == "move-right":
            return replace(self, longitude=self.longitude + MOVE_LONGITUDE_DELTA)
        return self


class Camera(Protocol):
    def capture(self, view: View) -> bytes:
        """A JPEG screenshot of the view."""


class Analyst(Protocol):
    def examine(
        self,
        image: bytes,
        country: str,
        earlier_reports: list[AnalystReport],
    ) -> tuple[AnalystReport, str]:
        """A report on the image, and the next action (one of ACTIONS)."""


def analyze_base(
    base: Base,
    camera: Camera,
    analyst: Analyst,
    overview_path: Path,
    max_analysts: int = MAX_ANALYSTS,
) -> list[AnalystReport]:
    """Run analysts over the Base until one says "finish" or max_analysts is reached.

    The first screenshot is saved to overview_path for the dashboard.
    """
    view = View(float(base.latitude), float(base.longitude))
    reports = []

    for turn in range(1, max_analysts + 1):
        image = camera.capture(view)

        if turn == 1:
            overview_path.parent.mkdir(parents=True, exist_ok=True)
            overview_path.write_bytes(image)

        report, action = analyst.examine(image, base.country, list(reports))
        reports.append(report)
        print(f"Action for base {base.id}, analysis {turn}: {action}")

        if action == "finish":
            break

        view = view.after(action)

    return reports
