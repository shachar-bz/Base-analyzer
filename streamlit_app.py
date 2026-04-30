import json
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

from Object_detection import detect_objects_in_image


DATA_PATH = Path("data.json")
SCREENSHOTS_DIR = Path("bases_screenshots")
MAP_PAGE_LABEL = "Map"
COUNTRY_FLAGS = {
    "Egypt": "\U0001f1ea\U0001f1ec",
    "Korea": "\U0001f1f0\U0001f1f7",
    "Russia": "\U0001f1f7\U0001f1fa",
}
COUNTRY_REGIONS = {
    "Egypt": "North Africa",
    "Korea": "East Asia",
    "Russia": "Eurasia",
}
DEFAULT_IMAGE_DATE = "Not available"
DEFAULT_CAMERA_ALTITUDE = "10.04969521a"
DEFAULT_SCALE = "1650d"


def apply_custom_css() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            width: 240px !important;
            min-width: 240px !important;
        }

        [data-testid="stSidebar"] > div:first-child {
            width: 240px !important;
            min-width: 240px !important;
        }

        [data-testid="stSidebar"] * {
            font-size: 14px !important;
        }

        [data-testid="stSidebar"] .stButton > button {
            background: transparent !important;
            color: inherit !important;
            border: 1px solid rgba(49, 51, 63, 0.2) !important;
        }

        .country-divider {
            border: 0;
            border-top: 1px solid rgba(49, 51, 63, 0.18);
            margin: 0.65rem 0;
        }

        .page-title {
            font-size: 28px;
            font-weight: 500;
            line-height: 1.25;
            margin: 0 0 0.75rem 0;
        }

        div[data-testid="stMarkdownContainer"],
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stMarkdownContainer"] li,
        .stText,
        p,
        li {
            font-size: 15px;
            line-height: 1.7;
        }

        button[data-baseweb="tab"] p {
            font-size: 14px !important;
        }

        .metadata-panel {
            border: 1px solid rgba(49, 51, 63, 0.16);
            border-radius: 8px;
            padding: 1rem;
            background: rgba(248, 249, 251, 0.7);
        }

        .metadata-row {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.45rem 0;
            border-bottom: 1px solid rgba(49, 51, 63, 0.08);
            font-size: 15px;
            line-height: 1.7;
        }

        .metadata-row:last-child {
            border-bottom: 0;
        }

        .metadata-label {
            color: rgba(49, 51, 63, 0.68);
            font-weight: 500;
        }

        .metadata-value {
            color: rgb(49, 51, 63);
            font-weight: 500;
            text-align: right;
        }

        .object-detection-title {
            font-size: 16px;
            font-weight: 500;
            line-height: 1.35;
            margin: 1.1rem 0 0.15rem 0;
        }

        .object-detection-description {
            color: rgba(49, 51, 63, 0.62);
            font-size: 13px;
            line-height: 1.45;
            margin: 0 0 0.55rem 0;
        }

        div[data-testid="stTextInput"] input {
            border: 1px solid rgba(37, 99, 235, 0.45) !important;
            border-radius: 6px !important;
        }

        section.main .stButton > button {
            background: #2563eb !important;
            color: #ffffff !important;
            border: 1px solid #2563eb !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
        }

        section.main .stButton > button:hover {
            background: #1d4ed8 !important;
            border-color: #1d4ed8 !important;
            color: #ffffff !important;
        }

        [data-testid="stDataFrame"] div[role="row"] {
            min-height: 44px !important;
        }

        [data-testid="stDataFrame"] div[role="gridcell"] {
            font-size: 14px !important;
            padding-top: 10px !important;
            padding-bottom: 10px !important;
        }

        [data-testid="stDataFrame"] div[role="columnheader"] {
            font-size: 14px !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_title(title: str) -> None:
    st.markdown(f'<h1 class="page-title">{escape(title)}</h1>', unsafe_allow_html=True)


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


def split_confidence_prefix(text: str) -> tuple[str | None, str]:
    confidence_prefixes = {
        "High confidence:": "high",
        "Medium confidence:": "medium",
        "Low confidence:": "low",
    }

    for prefix, confidence in confidence_prefixes.items():
        if text.startswith(prefix):
            return confidence, text[len(prefix) :].strip()

    return None, text


def confidence_dot(confidence: str | None) -> str:
    dot_colors = {
        "high": "#16a34a",
        "medium": "#d97706",
        "low": "#dc2626",
    }
    color = dot_colors.get(confidence)

    if not color:
        return ""

    return (
        f'<span style="display:inline-block;width:0.65rem;height:0.65rem;'
        f'border-radius:50%;background:{color};margin-right:0.45rem;"></span>'
    )


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
        confidence, text = split_confidence_prefix(item)
        dot = confidence_dot(confidence)
        st.markdown(
            f'<div class="analysis-bullet">{dot}{escape(text)}</div>',
            unsafe_allow_html=True,
        )


def base_label(base_id: str, base_data: dict[str, Any]) -> str:
    country = base_data.get("country") or "Unknown"
    return f"{country} - {base_id}"


def sort_base_id(base_id: str, base_data: dict[str, Any]) -> tuple[str, int, int | str]:
    country = str(base_data.get("country") or "")
    if str(base_id).isdigit():
        return (country, 0, int(base_id))

    return (country, 1, str(base_id))


def country_label(country: str) -> str:
    flag = COUNTRY_FLAGS.get(country)
    return f"{flag} {country}" if flag else country


def get_base_region(base_data: dict[str, Any]) -> str:
    explicit_region = base_data.get("region")
    if explicit_region:
        return str(explicit_region)

    country = str(base_data.get("country") or "Unknown")
    return COUNTRY_REGIONS.get(country, country)


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


def get_metadata_value(base_data: dict[str, Any], keys: tuple[str, ...], default: str) -> str:
    for key in keys:
        value = base_data.get(key)
        if value not in (None, ""):
            return str(value)

    return default


def render_metadata_panel(base_data: dict[str, Any]) -> None:
    metadata_rows = [
        ("Latitude", get_metadata_value(base_data, ("latitude",), "Unknown")),
        ("Longitude", get_metadata_value(base_data, ("longitude",), "Unknown")),
        (
            "Image date",
            get_metadata_value(
                base_data,
                ("image_date", "imageDate", "date"),
                DEFAULT_IMAGE_DATE,
            ),
        ),
        (
            "Camera altitude",
            get_metadata_value(
                base_data,
                ("camera_altitude", "cameraAltitude", "altitude"),
                DEFAULT_CAMERA_ALTITUDE,
            ),
        ),
        (
            "Scale",
            get_metadata_value(base_data, ("scale", "camera_distance"), DEFAULT_SCALE),
        ),
    ]
    rows_html = "".join(
        (
            '<div class="metadata-row">'
            f'<span class="metadata-label">{escape(label)}</span>'
            f'<span class="metadata-value">{escape(value)}</span>'
            "</div>"
        )
        for label, value in metadata_rows
    )

    st.markdown(f'<div class="metadata-panel">{rows_html}</div>', unsafe_allow_html=True)


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
    render_page_title("Military Bases Map")

    map_rows = build_map_rows(data)
    if not map_rows:
        st.warning("No bases with valid latitude and longitude were found.")
        return

    countries_count = len(
        {
            base_data.get("country")
            for base_data in data.values()
            if base_data.get("country")
        }
    )
    regions_count = len({get_base_region(base_data) for base_data in data.values()})

    total_bases_column, countries_column, regions_column = st.columns(3)
    total_bases_column.metric("Total Bases", len(data))
    countries_column.metric("Countries", countries_count)
    regions_column.metric("Regions", regions_count)

    st.map(map_rows, latitude="lat", longitude="lon", size=50, height=430)
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


def render_object_detection_section(
    base_id: str,
    image_path: Path,
    image_slot: st.delta_generator.DeltaGenerator,
) -> None:
    st.markdown(
        '<div class="object-detection-title">Detect objects in this image</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        (
            '<div class="object-detection-description">'
            "Enter any object to locate it within the satellite imagery"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    input_column, button_column = st.columns([3, 1])
    object_to_detect = input_column.text_input(
        "Object detection",
        label_visibility="collapsed",
        placeholder="e.g. vehicles, radar dish, buildings…",
        key=f"object-detection-{base_id}",
    )
    detect_clicked = button_column.button(
        "Detect ↗",
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

    render_page_title(f"{country} - {base_id}")

    image_path = get_base_image_path(base_id, base_data)
    image_column, metadata_column = st.columns([2, 1])

    with image_column:
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
) -> str:
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = MAP_PAGE_LABEL

    st.sidebar.button(
        MAP_PAGE_LABEL,
        key="nav-map",
        use_container_width=True,
        on_click=lambda: st.session_state.update(selected_page=MAP_PAGE_LABEL),
    )

    grouped_base_ids = group_base_ids_by_country(data, sorted_base_ids)
    sorted_countries = sorted(grouped_base_ids.keys())

    for country_index, country in enumerate(sorted_countries):
        if country_index:
            st.sidebar.markdown('<hr class="country-divider">', unsafe_allow_html=True)

        with st.sidebar.expander(country_label(country), expanded=True):
            for base_id in grouped_base_ids[country]:
                page_label = base_label(base_id, data[base_id])
                st.button(
                    f"Base {base_id}",
                    key=f"nav-base-{base_id}",
                    use_container_width=True,
                    on_click=lambda label=page_label: st.session_state.update(
                        selected_page=label,
                    ),
                )

    return st.session_state.selected_page


def main() -> None:
    st.set_page_config(page_title="Military Base Analyzer", layout="wide")
    apply_custom_css()
    data = load_base_data()

    sorted_base_ids = sorted(
        data.keys(),
        key=lambda base_id: sort_base_id(base_id, data[base_id]),
    )
    label_to_base_id = {
        base_label(base_id, data[base_id]): base_id for base_id in sorted_base_ids
    }
    selected_page = render_sidebar_navigation(data, sorted_base_ids)

    if selected_page == MAP_PAGE_LABEL or selected_page not in label_to_base_id:
        render_map_page(data)
        return

    selected_base_id = label_to_base_id[selected_page]
    render_base_page(selected_base_id, data[selected_base_id])


if __name__ == "__main__":
    main()
