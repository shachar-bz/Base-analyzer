import pytest

from base_analyzer.analysis_loop import START_DISTANCE_METERS, View, analyze_base
from base_analyzer.base_store import AnalystReport, Base


class FixtureCamera:
    def __init__(self) -> None:
        self.views: list[View] = []

    def capture(self, view: View) -> bytes:
        self.views.append(view)
        return f"image-{len(self.views)}".encode()


class ScriptedAnalyst:
    """Answers with the given actions in order, one per screenshot."""

    def __init__(self, *actions: str) -> None:
        self.actions = list(actions)
        self.seen: list[tuple[bytes, str, int]] = []

    def examine(self, image, country, earlier_reports):
        self.seen.append((image, country, len(earlier_reports)))
        report = AnalystReport(findings=[f"finding {len(self.seen)}"])
        return report, self.actions[len(self.seen) - 1]


BASE = Base(id="147", country="Egypt", latitude="23.95", longitude="32.99")


def test_stops_when_an_analyst_says_finish(tmp_path):
    camera = FixtureCamera()
    analyst = ScriptedAnalyst("zoom-in", "finish", "zoom-in")

    reports = analyze_base(BASE, camera, analyst, tmp_path / "overview.jpg")

    assert [report.findings for report in reports] == [["finding 1"], ["finding 2"]]
    assert len(camera.views) == 2


def test_stops_after_max_analysts(tmp_path):
    analyst = ScriptedAnalyst(*["zoom-out"] * 10)

    reports = analyze_base(BASE, FixtureCamera(), analyst, tmp_path / "overview.jpg", max_analysts=3)

    assert len(reports) == 3


def test_each_action_moves_the_next_view(tmp_path):
    camera = FixtureCamera()
    analyst = ScriptedAnalyst("zoom-in", "move-right", "finish")

    analyze_base(BASE, camera, analyst, tmp_path / "overview.jpg")

    first, zoomed, moved = camera.views
    assert first == View(23.95, 32.99, START_DISTANCE_METERS)
    assert zoomed.distance_meters < first.distance_meters
    assert moved.longitude > zoomed.longitude
    assert moved.distance_meters == zoomed.distance_meters


@pytest.mark.parametrize(
    ("action", "field", "direction"),
    [
        ("zoom-in", "distance_meters", -1),
        ("zoom-out", "distance_meters", 1),
        ("move-left", "longitude", -1),
        ("move-right", "longitude", 1),
    ],
)
def test_view_after_action(action, field, direction):
    view = View(23.95, 32.99)

    change = getattr(view.after(action), field) - getattr(view, field)

    assert change * direction > 0


def test_each_analyst_sees_the_earlier_reports_and_the_country(tmp_path):
    analyst = ScriptedAnalyst("zoom-in", "zoom-in", "finish")

    analyze_base(BASE, FixtureCamera(), analyst, tmp_path / "overview.jpg")

    assert analyst.seen == [
        (b"image-1", "Egypt", 0),
        (b"image-2", "Egypt", 1),
        (b"image-3", "Egypt", 2),
    ]


def test_first_screenshot_is_saved_as_the_overview(tmp_path):
    overview_path = tmp_path / "bases_screenshots" / "Egypt_147_base.jpg"

    analyze_base(BASE, FixtureCamera(), ScriptedAnalyst("zoom-in", "finish"), overview_path)

    assert overview_path.read_bytes() == b"image-1"
