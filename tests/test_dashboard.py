from streamlit.testing.v1 import AppTest

from base_analyzer.base_store import PROJECT_DIR, BaseStore


APP_PATH = str(PROJECT_DIR / "streamlit_app.py")


def run_app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=60).run()


def test_overview_page_renders():
    app = run_app()

    assert not app.exception
    assert app.title[0].value == "🌐 Global Overview"


def test_base_page_shows_commander_and_one_tab_per_analyst():
    base = next(iter(BaseStore().load().values()))
    app = run_app()

    app.button(key=f"nav-base-{base.id}").click().run()

    assert not app.exception
    assert app.title[0].value == f"📍 {base.country} - {base.id}"
    assert [tab.label for tab in app.tabs] == ["Commander"] + [
        f"Analysis {index}" for index in range(1, len(base.analyst_reports) + 1)
    ]
