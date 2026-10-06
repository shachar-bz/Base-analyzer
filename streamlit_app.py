import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import streamlit as st

from base_analyzer.object_detection import detect_objects_in_image


DATA_PATH = Path("data.json")
SCREENSHOTS_DIR = Path("bases_screenshots")
MAP_PAGE_LABEL = "🌐 Global Overview"
ANALYSIS_KEYS = {"analyst_history", "commander_summary"}


def render_page_title(title: str) -> None:
    st.title(title)


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


def sort_base_id(base_id: str, base_data: dict[str, Any]) -> tuple[str, int, int | str]:
    country = str(base_data.get("country") or "")
    if str(base_id).isdigit():
        return (country, 0, int(base_id))

    return (country, 1, str(base_id))


def group_base_ids_by_country(
    data: dict[str, dict[str, Any]],
    sorted_base_ids: list[str],
) -> dict[str, list[str]]:
    grouped_base_ids = defaultdict(list)

    for base_id in sorted_base_ids:
        country = data[base_id].get("country") or "Unknown"
        grouped_base_ids[str(country)].append(base_id)

    return dict(grouped_base_ids)


def get_base_image_path(base_id: str, base_data: dict[str, Any]) -> Path:
    country = base_data.get("country") or "Unknown"
    return SCREENSHOTS_DIR / f"{country}_{base_id}_base.jpg"


def is_displayable_metadata(value: Any) -> bool:
    return isinstance(value, str | int | float | bool) and value != ""


def humanize_key(key: str) -> str:
    return key.replace("_", " ").strip().title()


def render_metadata_panel(base_data: dict[str, Any]) -> None:
    metadata_rows = [
        {"Field": humanize_key(key), "Value": value}
        for key, value in base_data.items()
        if key not in ANALYSIS_KEYS and is_displayable_metadata(value)
    ]

    if metadata_rows:
        st.dataframe(metadata_rows, hide_index=True, use_container_width=True)
    else:
        st.caption("No metadata available.")


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


def collect_display_keys(data: dict[str, dict[str, Any]]) -> list[str]:
    display_keys = []

    for base_data in data.values():
        for key, value in base_data.items():
            if (
                key not in ANALYSIS_KEYS
                and key not in display_keys
                and is_displayable_metadata(value)
            ):
                display_keys.append(key)

    return display_keys


def build_table_rows(
    data: dict[str, dict[str, Any]],
    base_ids: list[str],
) -> list[dict[str, Any]]:
    display_keys = collect_display_keys(data)
    table_rows = []

    for base_id in base_ids:
        base_data = data[base_id]
        row = {"id": base_id}
        for key in display_keys:
            row[humanize_key(key)] = base_data.get(key, "")
        table_rows.append(row)

    return table_rows


def count_distinct_values(data: dict[str, dict[str, Any]], key: str) -> int:
    return len(
        {
            str(base_data[key])
            for base_data in data.values()
            if is_displayable_metadata(base_data.get(key))
        }
    )


def render_data_metrics(data: dict[str, dict[str, Any]]) -> None:
    metrics = [("Bases", len(data))]

    if any(is_displayable_metadata(base_data.get("country")) for base_data in data.values()):
        metrics.append(("Countries", count_distinct_values(data, "country")))

    if any(is_displayable_metadata(base_data.get("region")) for base_data in data.values()):
        metrics.append(("Regions", count_distinct_values(data, "region")))

    columns = st.columns(len(metrics))
    for column, (label, value) in zip(columns, metrics):
        column.metric(label, value)


def render_map_page(data: dict[str, dict[str, Any]]) -> None:
    render_page_title("🌐 Global Overview")

    map_rows = build_map_rows(data)
    if not map_rows:
        st.warning("No bases with valid latitude and longitude were found.")
        return

    sorted_base_ids = sorted(
        data.keys(),
        key=lambda base_id: sort_base_id(base_id, data[base_id]),
    )

    _, map_column, _ = st.columns([1, 3, 1])
    with map_column:
        render_data_metrics(data)
        st.subheader("🗺️ Map")
        st.map(map_rows, latitude="lat", longitude="lon", size=50, height=380)

    st.subheader("Bases")
    st.dataframe(
        build_table_rows(data, sorted_base_ids),
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

    st.subheader("🧠 Commander Analysis")
    render_bullets(commander_summary.get("supported_observations"))

    st.subheader("✅ Recommendations")
    render_bullets(commander_summary.get("recommendations"))


def render_analyst_tab(analysis_record: dict[str, Any]) -> None:
    st.subheader("Findings")
    render_bullets(analysis_record.get("findings"))

    st.subheader("Analysis")
    render_bullets(analysis_record.get("analysis"))

    st.subheader("Things To Continue Analyze")
    render_bullets(analysis_record.get("things_to_continue_analyzing"))


def render_object_detection_section(
    base_id: str,
    image_path: Path,
    image_slot: st.delta_generator.DeltaGenerator,
) -> None:
    st.subheader("Detect objects in this image")
    st.caption("Enter any object to locate it within the satellite imagery.")

    input_column, button_column = st.columns([3, 1])
    object_to_detect = input_column.text_input(
        "Object detection",
        label_visibility="collapsed",
        placeholder="e.g. vehicles, radar dish, buildings...",
        key=f"object-detection-{base_id}",
    )
    detect_clicked = button_column.button(
        "Detect",
        key=f"detect-button-{base_id}",
        use_container_width=True,
    )

    if not image_path.exists():
        return

    detection_result_key = f"detection-result-{base_id}"
    cleaned_object_to_detect = object_to_detect.strip()

    if detect_clicked and not cleaned_object_to_detect:
        st.warning("Enter an object to detect first.")
        return

    if detect_clicked:
        try:
            with st.spinner(f"Detecting {cleaned_object_to_detect}..."):
                annotated_image, detection_count = detect_objects_in_image(
                    image_path,
                    cleaned_object_to_detect,
                )

            if detection_count:
                st.session_state[detection_result_key] = {
                    "image": annotated_image,
                    "caption": (
                        f"{image_path.name} - detected {detection_count} "
                        f"{cleaned_object_to_detect}"
                    ),
                }
                image_slot.image(
                    annotated_image,
                    caption=st.session_state[detection_result_key]["caption"],
                    use_container_width=True,
                )
                st.success(
                    f"Detected {detection_count} objects for: {cleaned_object_to_detect}"
                )
            else:
                st.info(f"No objects detected for: {cleaned_object_to_detect}")
        except Exception as error:
            st.error(f"Could not detect {cleaned_object_to_detect}: {error}")


def render_base_page(base_id: str, base_data: dict[str, Any]) -> None:
    country = base_data.get("country") or "Unknown"
    analyst_history = as_list(base_data.get("analyst_history"))
    commander_summary = base_data.get("commander_summary") or {}

    if not isinstance(commander_summary, dict):
        commander_summary = {}

    render_page_title(f"📍 {country} - {base_id}")

    image_path = get_base_image_path(base_id, base_data)
    image_column, metadata_column = st.columns([2, 1])

    with image_column:
        st.subheader("🛰️ Satellite Map")
        image_slot = st.empty()
        detection_result = st.session_state.get(f"detection-result-{base_id}")

        if image_path.exists() and detection_result:
            image_slot.image(
                detection_result["image"],
                caption=detection_result["caption"],
                use_container_width=True,
            )
        elif image_path.exists():
            image_slot.image(str(image_path), caption=image_path.name, use_container_width=True)
        else:
            st.warning(f"Screenshot not found: {image_path}")

    with metadata_column:
        st.subheader("Details")
        render_metadata_panel(base_data)

    render_object_detection_section(base_id, image_path, image_slot)

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


def render_sidebar_navigation(
    data: dict[str, dict[str, Any]],
    sorted_base_ids: list[str],
) -> str | None:
    if "selected_base_id" not in st.session_state:
        st.session_state.selected_base_id = None

    st.sidebar.title("Military Base Analyzer")
    st.sidebar.button(
        MAP_PAGE_LABEL,
        key="nav-map",
        use_container_width=True,
        on_click=lambda: st.session_state.update(selected_base_id=None),
    )

    grouped_base_ids = group_base_ids_by_country(data, sorted_base_ids)
    sorted_countries = sorted(grouped_base_ids.keys())

    for country in sorted_countries:
        with st.sidebar.expander(country, expanded=False):
            for base_id in grouped_base_ids[country]:
                st.button(
                    f"Base {base_id}",
                    key=f"nav-base-{base_id}",
                    use_container_width=True,
                    on_click=lambda selected_base_id=base_id: st.session_state.update(
                        selected_base_id=selected_base_id,
                    ),
                )

    selected_base_id = st.session_state.selected_base_id
    return selected_base_id if selected_base_id in data else None


def main() -> None:
    st.set_page_config(page_title="Military Base Analyzer", layout="wide")
    data = load_base_data()

    sorted_base_ids = sorted(
        data.keys(),
        key=lambda base_id: sort_base_id(base_id, data[base_id]),
    )
    selected_base_id = render_sidebar_navigation(data, sorted_base_ids)

    if selected_base_id is None:
        render_map_page(data)
        return

    render_base_page(selected_base_id, data[selected_base_id])


if __name__ == "__main__":
    main()
