"""Analyze the bases listed in a CSV file and add them to data.json.

Usage: python -m base_analyzer [--csv PATH] [--limit N]
"""

import argparse
import csv
from itertools import islice
from pathlib import Path

from dotenv import load_dotenv

from base_analyzer.analysis_loop import analyze_base
from base_analyzer.analyst import InvalidReplyError, OpenAIAnalyst, openai_client, summarize
from base_analyzer.base_store import PROJECT_DIR, UNKNOWN_COUNTRY, Base, BaseStore
from base_analyzer.camera import GoogleEarthBlocked, GoogleEarthCamera


CSV_PATH = PROJECT_DIR / "military_bases.csv"
ROWS_TO_PROCESS = 16


def read_base_list(csv_path: Path, rows_to_process: int = ROWS_TO_PROCESS) -> list[Base]:
    """The first rows_to_process Bases in a CSV with id, country, latitude and longitude columns."""
    bases = []

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        for row in islice(csv.DictReader(csv_file), rows_to_process):
            bases.append(
                Base(
                    id=(row.get("id") or "").strip(),
                    country=(row.get("country") or "").strip() or UNKNOWN_COUNTRY,
                    latitude=(row.get("latitude") or "").strip(),
                    longitude=(row.get("longitude") or "").strip(),
                )
            )

    return bases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=CSV_PATH, help="bases to analyze")
    parser.add_argument(
        "--limit",
        type=int,
        default=ROWS_TO_PROCESS,
        help="read at most this many CSV rows",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"{args.csv} not found. See README.md for the expected columns.")

    load_dotenv()
    client = openai_client()
    analyst = OpenAIAnalyst(client)
    store = BaseStore()
    analyzed_bases = store.load()

    for base in read_base_list(args.csv, args.limit):
        if base.id in analyzed_bases:
            print(f"Skipping base {base.id}; already in {store.data_path.name}.")
            continue

        try:
            with GoogleEarthCamera() as camera:
                base.analyst_reports = analyze_base(
                    base,
                    camera,
                    analyst,
                    store.screenshot_path(base),
                )
            base.commander_summary = summarize(base.analyst_reports, client)
        except InvalidReplyError as error:
            print(f"Skipping base {base.id} ({base.country}): {error}")
            continue
        except GoogleEarthBlocked as error:
            raise SystemExit(f"Stopped at base {base.id} ({base.country}): {error}") from error

        analyzed_bases[base.id] = base
        store.save(analyzed_bases)


if __name__ == "__main__":
    main()
