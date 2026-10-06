from base_analyzer.__main__ import read_base_list
from base_analyzer.analysis_loop import View
from base_analyzer.camera import google_earth_url


def test_read_base_list_reads_rows_up_to_the_limit(tmp_path):
    csv_path = tmp_path / "bases.csv"
    csv_path.write_text(
        "id,country,latitude,longitude\n"
        "147, Egypt ,23.95,32.99\n"
        "148,,24.00,33.00\n"
        "149,Syria,35.00,36.00\n",
        encoding="utf-8",
    )

    bases = read_base_list(csv_path, rows_to_process=2)

    assert [(base.id, base.country, base.latitude) for base in bases] == [
        ("147", "Egypt", "23.95"),
        ("148", "Unknown", "24.00"),
    ]


def test_google_earth_url_points_at_the_view():
    url = google_earth_url(View(23.95, 32.99, 1650.0))

    assert url == (
        "https://earth.google.com/web/@23.95,32.99,"
        "10.04969521a,1650.0d,30.00000016y,-0h,0t,0r"
    )
