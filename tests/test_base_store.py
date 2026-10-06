import json

import pytest

from base_analyzer.base_store import (
    PROJECT_DIR,
    AnalystReport,
    Base,
    BaseStore,
    CommanderSummary,
)


def make_base(**overrides) -> Base:
    fields = {
        "id": "147",
        "country": "Egypt",
        "latitude": "23.95",
        "longitude": "32.99",
        "analyst_reports": [
            AnalystReport(
                findings=["Runway"],
                analysis="One long runway.",
                things_to_continue_analyzing=["Hangars"],
            )
        ],
        "commander_summary": CommanderSummary(
            summary="Likely an airbase.",
            supported_observations=["High confidence: a runway"],
            recommendations=["Zoom in on the hangars"],
        ),
    }
    fields.update(overrides)
    return Base(**fields)


def test_saved_bases_load_back_equal(tmp_path):
    store = BaseStore(tmp_path)
    bases = {"147": make_base(), "1038": make_base(id="1038", country="Syria")}

    store.save(bases)

    assert store.load() == bases


def test_project_data_round_trips_byte_for_byte(tmp_path):
    original = (PROJECT_DIR / "data.json").read_text(encoding="utf-8")
    store = BaseStore(tmp_path)
    store.data_path.write_text(original, encoding="utf-8")

    store.save(store.load())

    assert store.data_path.read_text(encoding="utf-8") == original


def test_missing_data_file_loads_as_no_bases(tmp_path):
    assert BaseStore(tmp_path).load() == {}


def test_invalid_json_raises_instead_of_loading_as_no_bases(tmp_path):
    store = BaseStore(tmp_path)
    store.data_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        store.load()


def test_screenshot_path_names_country_and_id(tmp_path):
    path = BaseStore(tmp_path).screenshot_path(make_base())

    assert path == tmp_path / "bases_screenshots" / "Egypt_147_base.jpg"


def test_blank_country_reads_as_unknown():
    assert Base.from_dict("147", {"country": ""}).country == "Unknown"
