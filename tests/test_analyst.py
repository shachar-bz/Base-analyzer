import json
from types import SimpleNamespace

import pytest

from base_analyzer.analyst import (
    InvalidReplyError,
    OpenAIAnalyst,
    analyst_prompt,
    parse_json_reply,
    summarize,
)
from base_analyzer.base_store import AnalystReport, CommanderSummary


class FakeOpenAI:
    """Stands in for the OpenAI client: replies with fixed text, records requests."""

    def __init__(self, reply_text: str) -> None:
        self.requests: list[dict] = []
        self.responses = SimpleNamespace(create=self._create)
        self._reply_text = reply_text

    def _create(self, **request):
        self.requests.append(request)
        return SimpleNamespace(output_text=self._reply_text)


ANALYST_REPLY = {
    "findings": ["Runway"],
    "analysis": ["One long runway"],
    "things_to_continue_analyzing": ["Hangars"],
    "action": "zoom-in",
}


def test_parse_json_reply_ignores_code_fences():
    assert parse_json_reply('```json\n{"action": "finish"}\n```') == {"action": "finish"}


@pytest.mark.parametrize("reply_text", ["Sorry, I can't help with that.", '{"findings": [}'])
def test_parse_json_reply_rejects_non_json(reply_text):
    with pytest.raises(InvalidReplyError):
        parse_json_reply(reply_text)


def test_examine_returns_report_and_action():
    analyst = OpenAIAnalyst(FakeOpenAI(json.dumps(ANALYST_REPLY)))

    report, action = analyst.examine(b"jpeg", "Egypt", [])

    assert report == AnalystReport(
        findings=["Runway"],
        analysis=["One long runway"],
        things_to_continue_analyzing=["Hangars"],
    )
    assert action == "zoom-in"


def test_examine_treats_unknown_action_as_finish():
    analyst = OpenAIAnalyst(FakeOpenAI(json.dumps({**ANALYST_REPLY, "action": "fly-away"})))

    _, action = analyst.examine(b"jpeg", "Egypt", [])

    assert action == "finish"


def test_examine_sends_the_image_and_prompt():
    client = FakeOpenAI(json.dumps(ANALYST_REPLY))

    OpenAIAnalyst(client).examine(b"jpeg", "Egypt", [])

    text_part, image_part = client.requests[0]["input"][0]["content"]
    assert "military of Egypt" in text_part["text"]
    assert image_part["image_url"] == "data:image/jpeg;base64,anBlZw=="


def test_first_analyst_prompt_has_no_earlier_reports():
    assert "previous analysts" not in analyst_prompt("Egypt", [])


def test_later_analyst_prompts_include_earlier_findings():
    earlier = [AnalystReport(findings=["Fuel depot"], things_to_continue_analyzing=["Trucks"])]

    prompt = analyst_prompt("Egypt", earlier)

    assert prompt.startswith("Here is the analysis of previous analysts")
    assert "Fuel depot" in prompt and "Trucks" in prompt


def test_summarize_returns_commander_summary():
    reply = {
        "summary": "Likely an airbase.",
        "supported_observations": ["High confidence: a runway"],
        "recommendations": ["Zoom in on the hangars"],
    }
    client = FakeOpenAI(json.dumps(reply))

    summary = summarize([AnalystReport(findings=["Runway"])], client)

    assert summary == CommanderSummary(**reply)
    assert "Runway" in client.requests[0]["input"][0]["content"][0]["text"]
