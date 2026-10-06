import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import streamlit as st

from base_analyzer.analysis_loop import View
from base_analyzer.base_store import AnalystReport, Base, BaseStore, CommanderSummary
from base_analyzer.camera import google_earth_url
from base_analyzer.object_detection import detect_objects_in_image


MAP_PAGE_LABEL = "🌐 Global Overview"

store = BaseStore()


def load_bases() -> dict[str, Base]:
    try:
        return store.load()
    except json.JSONDecodeError:
        st.error(f"{store.data_path.name} is not valid JSON.")
        return {}


def clean_list_item(value: Any) -> str:
    text = str(value).strip()
    return text[1:].strip() if text.startswith("-") else text


def render_bullets(items: list[str] | str, empty_text: str = "No data available.") -> None:
    items = [items] if isinstance(items, str) else items
    cleaned_items = [clean_list_item(item) for item in items]
    cleaned_items = [item for item in cleaned_items if item]

    if not cleaned_items:
        st.caption(empty_text)
        return

    for item in cleaned_items:
        st.markdown(f"- {item}")


def sort_key(base: Base) -> tuple[str, int, int | str]:
    if base.id.isdigit():
        return (base.country, 0, int(base.id))

    return (base.country, 1, base.id)


def group_by_country(sorted_bases: list[Base]) -> dict[str, list[Base]]:
    grouped_bases = defaultdict(list)

    for base in sorted_bases:
        grouped_bases[base.country].append(base)

    return dict(grouped_bases)


def base_details(base: Base) -> dict[str, str]:
    return {"Country": base.country, "Latitude": base.latitude, "Longitude": base.longitude}


def coordinates(base: Base) -> tuple[float, float] | None:
    try:
        return float(base.latitude), float(base.longitude)
    except ValueError:
        return None


def build_map_rows(bases: list[Base]) -> list[dict[str, Any]]:
    map_rows = []

    for base in bases:
        base_coordinates = coordinates(base)
        if base_coordinates is None:
            continue

        latitude, longitude = base_coordinates
        map_rows.append({"id": base.id, "country": base.country, "lat": latitude, "lon": longitude})

    return map_rows


def render_map_page(sorted_bases: list[Base]) -> None:
    st.title(MAP_PAGE_LABEL)

    map_rows = build_map_rows(sorted_bases)
    if not map_rows:
        st.warning("No bases with valid latitude and longitude were found.")
        return

    _, map_column, _ = st.columns([1, 3, 1])
    with map_column:
        bases_column, countries_column = st.columns(2)
        bases_column.metric("Bases", len(sorted_bases))
        countries_column.metric("Countries", len({base.country for base in sorted_bases}))
        st.subheader("🗺️ Map")
        st.map(map_rows, latitude="lat", longitude="lon", size=50, height=380)

    st.subheader("Bases")
    st.dataframe(
        [{"id": base.id, **base_details(base)} for base in sorted_bases],
        hide_index=True,
    )


def render_commander_tab(commander_summary: CommanderSummary) -> None:
    st.subheader("Summary")
    if commander_summary.summary:
        st.write(commander_summary.summary)
    else:
        st.caption("No summary available.")

    st.subheader("🧠 Commander Analysis")
    render_bullets(commander_summary.supported_observations)

    st.subheader("✅ Recommendations")
    render_bullets(commander_summary.recommendations)


def render_analyst_tab(report: AnalystReport) -> None:
    st.subheader("Findings")
    render_bullets(report.findings)

    st.subheader("Analysis")
    render_bullets(report.analysis)

    st.subheader("Things To Continue Analyze")
    render_bullets(report.things_to_continue_analyzing)


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
        width="stretch",
    )

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
                    width="stretch",
                )
                st.success(
                    f"Detected {detection_count} objects for: {cleaned_object_to_detect}"
                )
            else:
                st.info(f"No objects detected for: {cleaned_object_to_detect}")
        except Exception as error:
            st.error(f"Could not detect {cleaned_object_to_detect}: {error}")


def render_base_page(base: Base) -> None:
    st.title(f"📍 {base.country} - {base.id}")

    image_path = store.screenshot_path(base)
    image_column, details_column = st.columns([2, 1])

    with image_column:
        st.subheader("🛰️ Satellite Map")
        image_slot = st.empty()
        detection_result = st.session_state.get(f"detection-result-{base.id}")

        if image_path.exists() and detection_result:
            image_slot.image(
                detection_result["image"],
                caption=detection_result["caption"],
                width="stretch",
            )
        elif image_path.exists():
            image_slot.image(str(image_path), caption=image_path.name, width="stretch")
        else:
            st.info("No screenshot for this base. Run the collector to take one.")
            base_coordinates = coordinates(base)
            if base_coordinates is not None:
                st.link_button("Open in Google Earth", google_earth_url(View(*base_coordinates)))

    with details_column:
        st.subheader("Details")
        st.dataframe(
            [{"Field": field, "Value": value} for field, value in base_details(base).items()],
            hide_index=True,
        )

    if image_path.exists():
        render_object_detection_section(base.id, image_path, image_slot)

    tab_names = ["Commander"] + [
        f"Analysis {index}" for index in range(1, len(base.analyst_reports) + 1)
    ]
    tabs = st.tabs(tab_names)

    with tabs[0]:
        render_commander_tab(base.commander_summary)

    for tab, report in zip(tabs[1:], base.analyst_reports):
        with tab:
            render_analyst_tab(report)


def render_sidebar_navigation(
    bases: dict[str, Base],
    sorted_bases: list[Base],
) -> Base | None:
    if "selected_base_id" not in st.session_state:
        st.session_state.selected_base_id = None

    st.sidebar.title("Military Base Analyzer")
    st.sidebar.button(
        MAP_PAGE_LABEL,
        key="nav-map",
        width="stretch",
        on_click=lambda: st.session_state.update(selected_base_id=None),
    )

    grouped_bases = group_by_country(sorted_bases)

    for country in sorted(grouped_bases):
        with st.sidebar.expander(country, expanded=False):
            for base in grouped_bases[country]:
                st.button(
                    f"Base {base.id}",
                    key=f"nav-base-{base.id}",
                    width="stretch",
                    on_click=lambda selected_base_id=base.id: st.session_state.update(
                        selected_base_id=selected_base_id,
                    ),
                )

    return bases.get(st.session_state.selected_base_id)


def main() -> None:
    st.set_page_config(page_title="Military Base Analyzer", layout="wide")
    bases = load_bases()
    sorted_bases = sorted(bases.values(), key=sort_key)
    selected_base = render_sidebar_navigation(bases, sorted_bases)

    if selected_base is None:
        render_map_page(sorted_bases)
        return

    render_base_page(selected_base)


if __name__ == "__main__":
    main()
