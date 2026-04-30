import json
from pathlib import Path
from typing import Any

import streamlit as st


DATA_PATH = Path("data.json")
SCREENSHOTS_DIR = Path("bases_screenshots")
MAP_PAGE_LABEL = "Map"


def load_base_data() -> dict[str, dict[str, Any]]:
    if not DATA_PATH.exists():
        st.error(f"Could not find {DATA_PATH}.")
        return {}

    try:
        with DATA_PATH.open(encoding="utf-8") as data_file:
            data = json.load(data_file)
    except json.JSONDecodeError:
        st.error(f"{DATA_PATH} is not valid JSON.")
        return {}

    if not isinstance(data, dict):
        st.error(f"{DATA_PATH} must contain a JSON object keyed by base id.")
        return {}

    return data


def parse_coordinate(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean_list_item(value: Any) -> str:
    text = str(value).strip()
    return text[1:].strip() if text.startswith("-") else text


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def render_bullets(items: Any, empty_text: str = "No data available.") -> None:
    cleaned_items = [clean_list_item(item) for item in as_list(items)]
    cleaned_items = [item for item in cleaned_items if item]

    if not cleaned_items:
        st.caption(empty_text)
        return

    for item in cleaned_items:
        st.markdown(f"- {item}")


def base_label(base_id: str, base_data: dict[str, Any]) -> str:
    country = base_data.get("country") or "Unknown"
    return f"{country} - {base_id}"


def sort_base_id(base_id: str, base_data: dict[str, Any]) -> tuple[str, int, int | str]:
    country = str(base_data.get("country") or "")
    if str(base_id).isdigit():
        return (country, 0, int(base_id))

    return (country, 1, str(base_id))


def get_base_image_path(base_id: str, base_data: dict[str, Any]) -> Path:
    country = base_data.get("country") or "Unknown"
    return SCREENSHOTS_DIR / f"{country}_{base_id}_base.jpg"


def build_map_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    map_rows = []

    for base_id, base_data in data.items():
        latitude = parse_coordinate(base_data.get("latitude"))
        longitude = parse_coordinate(base_data.get("longitude"))

        if latitude is None or longitude is None:
            continue

        map_rows.append(
            {
                "id": base_id,
                "country": base_data.get("country") or "Unknown",
                "lat": latitude,
                "lon": longitude,
            }
        )

    return map_rows


def render_map_page(data: dict[str, dict[str, Any]]) -> None:
    st.title("Military Bases Map")

    map_rows = build_map_rows(data)
    if not map_rows:
        st.warning("No bases with valid latitude and longitude were found.")
        return

    st.map(map_rows, latitude="lat", longitude="lon", size=50)
    st.dataframe(
        map_rows,
        column_order=("country", "id", "lat", "lon"),
        hide_index=True,
        use_container_width=True,
    )


def render_commander_tab(commander_summary: dict[str, Any]) -> None:
    st.subheader("Summary")
    summary = commander_summary.get("summary")
    if summary:
        st.write(summary)
    else:
        st.caption("No summary available.")

    st.subheader("Commander Analysis")
    render_bullets(commander_summary.get("supported_observations"))

    st.subheader("Recommendations")
    render_bullets(commander_summary.get("recommendations"))


def render_analyst_tab(analysis_record: dict[str, Any]) -> None:
    st.subheader("Findings")
    render_bullets(analysis_record.get("findings"))

    st.subheader("Analysis")
    render_bullets(analysis_record.get("analysis"))

    st.subheader("Things To Continue Analyze")
    render_bullets(analysis_record.get("things_to_continue_analyzing"))


def render_base_page(base_id: str, base_data: dict[str, Any]) -> None:
    country = base_data.get("country") or "Unknown"
    latitude = base_data.get("latitude", "Unknown")
    longitude = base_data.get("longitude", "Unknown")
    analyst_history = as_list(base_data.get("analyst_history"))
    commander_summary = base_data.get("commander_summary") or {}

    if not isinstance(commander_summary, dict):
        commander_summary = {}

    st.title(f"{country} - {base_id}")
    st.caption(f"Latitude: {latitude} | Longitude: {longitude}")

    image_path = get_base_image_path(base_id, base_data)
    if image_path.exists():
        st.image(str(image_path), caption=image_path.name, use_container_width=True)
    else:
        st.warning(f"Screenshot not found: {image_path}")

    tab_names = ["Commander"] + [
        f"Analysis {index}" for index in range(1, len(analyst_history) + 1)
    ]
    tabs = st.tabs(tab_names)

    with tabs[0]:
        render_commander_tab(commander_summary)

    for tab, analysis_record in zip(tabs[1:], analyst_history):
        with tab:
            if isinstance(analysis_record, dict):
                render_analyst_tab(analysis_record)
            else:
                st.caption("No analyst data available.")


def main() -> None:
    st.set_page_config(page_title="Military Base Analyzer", layout="wide")
    data = load_base_data()

    sorted_base_ids = sorted(
        data.keys(),
        key=lambda base_id: sort_base_id(base_id, data[base_id]),
    )
    label_to_base_id = {
        base_label(base_id, data[base_id]): base_id for base_id in sorted_base_ids
    }
    navigation_options = [MAP_PAGE_LABEL] + list(label_to_base_id.keys())

    selected_page = st.sidebar.radio("Navigation", navigation_options)

    if selected_page == MAP_PAGE_LABEL:
        render_map_page(data)
        return

    selected_base_id = label_to_base_id[selected_page]
    render_base_page(selected_base_id, data[selected_base_id])


if __name__ == "__main__":
    main()
