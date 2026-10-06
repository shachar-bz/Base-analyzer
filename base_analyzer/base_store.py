"""The Base store: every file an analyzed Base lives in.

data.json holds one record per Base, keyed by Base id, and bases_screenshots/
holds one overview screenshot per Base. The collector writes both and the
dashboard reads both, so the file layout and naming rules live only here.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
UNKNOWN_COUNTRY = "Unknown"


@dataclass
class AnalystReport:
    """What one analyst saw in one screenshot of a Base."""

    findings: list[str] = field(default_factory=list)
    # Usually a list of lines, but some analysts answered with one string.
    analysis: list[str] | str = field(default_factory=list)
    things_to_continue_analyzing: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, record: dict) -> "AnalystReport":
        return cls(
            findings=record.get("findings", []),
            analysis=record.get("analysis", []),
            things_to_continue_analyzing=record.get("things_to_continue_analyzing", []),
        )

    def to_dict(self) -> dict:
        return {
            "findings": self.findings,
            "analysis": self.analysis,
            "things_to_continue_analyzing": self.things_to_continue_analyzing,
        }


@dataclass
class CommanderSummary:
    """The commander's conclusion after reading every AnalystReport for a Base."""

    summary: str = ""
    supported_observations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, record: dict) -> "CommanderSummary":
        return cls(
            summary=record.get("summary", ""),
            supported_observations=record.get("supported_observations", []),
            recommendations=record.get("recommendations", []),
        )

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "supported_observations": self.supported_observations,
            "recommendations": self.recommendations,
        }


@dataclass
class Base:
    """A suspected military base and what the analysts found there."""

    id: str
    country: str
    # Kept as the source text so data.json round-trips unchanged.
    latitude: str
    longitude: str
    analyst_reports: list[AnalystReport] = field(default_factory=list)
    commander_summary: CommanderSummary = field(default_factory=CommanderSummary)

    @classmethod
    def from_dict(cls, base_id: str, record: dict) -> "Base":
        return cls(
            id=base_id,
            country=record.get("country") or UNKNOWN_COUNTRY,
            latitude=record.get("latitude", ""),
            longitude=record.get("longitude", ""),
            analyst_reports=[
                AnalystReport.from_dict(report) for report in record.get("analyst_history", [])
            ],
            commander_summary=CommanderSummary.from_dict(record.get("commander_summary") or {}),
        )

    def to_dict(self) -> dict:
        return {
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "analyst_history": [report.to_dict() for report in self.analyst_reports],
            "commander_summary": self.commander_summary.to_dict(),
        }


class BaseStore:
    def __init__(self, root: Path = PROJECT_DIR) -> None:
        self.data_path = root / "data.json"
        self.screenshots_dir = root / "bases_screenshots"

    def load(self) -> dict[str, Base]:
        """Every analyzed Base, keyed by id. Invalid JSON raises instead of
        reading as empty, so a later save() can't overwrite the file with less."""
        if not self.data_path.exists():
            return {}

        with self.data_path.open(encoding="utf-8") as data_file:
            records = json.load(data_file)

        return {base_id: Base.from_dict(base_id, record) for base_id, record in records.items()}

    def save(self, bases: dict[str, Base]) -> None:
        records = {base_id: base.to_dict() for base_id, base in bases.items()}
        temporary_path = self.data_path.with_suffix(".json.tmp")

        with temporary_path.open("w", encoding="utf-8") as data_file:
            json.dump(records, data_file, indent=2)

        # Replace in one step so a crash mid-write never leaves half a file.
        os.replace(temporary_path, self.data_path)

    def screenshot_path(self, base: Base) -> Path:
        return self.screenshots_dir / f"{base.country}_{base.id}_base.jpg"
