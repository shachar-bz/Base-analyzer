"""Analyst and commander adapters: OpenAI models that read screenshots and reports."""

import base64
import json
import os

from openai import OpenAI

from base_analyzer.analysis_loop import ACTIONS
from base_analyzer.base_store import AnalystReport, CommanderSummary


ANALYST_MODEL = "gpt-5-nano"
COMMANDER_MODEL = "gpt-5.4-nano"

EARLIER_REPORTS_PREAMBLE = """Here is the analysis of previous analysts about this area and their recommendations on what else is needed to investigate, You can use this data but dont use it as fact, think for yourself:{earlier_reports}
"""

ANALYST_PROMPT_TEMPLATE = """You are an expert in understanding satellite imagery and you work for the US army.
We got intel that this area is a base/facility of the military of {country_name}.
Analyze this image and respond ONLY with a JSON object containing the following keys:
1. 'findings': A list of findings that you think are important for the US army to know, including
all man-made structures, military equipment, and infrastructure make sure to start each finding in a new line.
2. 'analysis': A detailed analysis of your findings make sure to start each finding in a new line.
3. 'things_to_continue_analyzing': A list of things that you think are important to continue
analyzing in further images make sure to start each thing in a new line.
4. 'action': One of ['zoom-in', 'zoom-out', 'move-left', 'move-right', 'finish'] based on what
would help you analyze the image or area better.
- Choose 'zoom-in' if you need to zoom in the image
- Choose 'zoom-out' if you need more context of the surrounding area or if you are zoomedin too much
- Choose 'move-left' or 'move-right' if you suspect there are important features just outside the current view
- Choose 'finish' if you have a complete understanding of the location Choose 'finish' if you think you have enough information about the base.
Respond ONLY with valid JSON. Do not include explanations or extra text.
"""

COMMANDER_PROMPT_TEMPLATE = """You are the commander of a team of imagery analysts.
You are reviewing multiple analyst reports about the same suspected military base or facility. Each report was written by a different analyst and may contain correct observations, uncertainty, or speculation.
Your job is to compare all analyst reports, identify what is strongly supported, separate facts from guesses, assign certainty levels, and produce one final commander-level conclusion.
Use the analyst reports as evidence, but do not blindly trust them. Think independently and avoid overclaiming.
Return only one valid JSON object. Do not include markdown, explanations, code blocks, backticks, or any text before or after the JSON.
Your response must use exactly this structure:

{{
  "summary": "Overall explanation of what the site most likely is, what it appears to contain, and its likely purpose. Mention uncertainty where needed.",
  "supported_observations": [
    "Observation with certainty level, for example: High confidence: The site includes a secured perimeter compound.",
    "Medium confidence: The site appears to contain internal roads and organized access routes.",
    "Low confidence: Some structures may be storage pads or equipment positions, but this is not confirmed."
  ],
  "recommendations": [
    "Specific next step for further imagery analysis, such as zooming into unclear structures, checking nearby roads, confirming vehicle types, or examining possible antennas/bunkers."
  ]
}}

Rules:
- Focus on consensus between analysts.
- Mark each supported observation with a certainty level: High confidence, Medium confidence, or Low confidence.
- Do not treat speculation as fact.
- Do not invent details that were not mentioned or visible.
- Do not include operational or attack recommendations.
- Recommendations should only describe what should be investigated further in imagery.
- Keep the answer professional, concise, and analytical.

Analyst reports:
{history_of_analysts}
"""


class InvalidReplyError(ValueError):
    """The model did not reply with the JSON object its prompt asked for."""


def openai_client() -> OpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")

    return OpenAI()


def parse_json_reply(reply_text: str) -> dict:
    """The JSON object in a reply, ignoring ```json fences or text around it."""
    start = reply_text.find("{")
    end = reply_text.rfind("}")

    try:
        if start == -1 or end < start:
            raise ValueError("no JSON object")
        return json.loads(reply_text[start : end + 1])
    except ValueError as error:
        raise InvalidReplyError(f"Expected a JSON object, got: {reply_text[:200]!r}") from error


def analyst_prompt(country: str, earlier_reports: list[AnalystReport]) -> str:
    prompt = ANALYST_PROMPT_TEMPLATE.format(country_name=country)
    if not earlier_reports:
        return prompt

    earlier = json.dumps(
        [
            {
                "findings": report.findings,
                "things_to_continue_analyzing": report.things_to_continue_analyzing,
            }
            for report in earlier_reports
        ]
    )
    return EARLIER_REPORTS_PREAMBLE.format(earlier_reports=earlier) + prompt


class OpenAIAnalyst:
    """Analyst adapter: one OpenAI vision call per screenshot."""

    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def examine(
        self,
        image: bytes,
        country: str,
        earlier_reports: list[AnalystReport],
    ) -> tuple[AnalystReport, str]:
        image_url = "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")
        response = self.client.responses.create(
            model=ANALYST_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": analyst_prompt(country, earlier_reports)},
                        {"type": "input_image", "image_url": image_url},
                    ],
                }
            ],
        )
        reply = parse_json_reply(response.output_text)
        action = reply.get("action")

        return AnalystReport.from_dict(reply), action if action in ACTIONS else "finish"


def summarize(reports: list[AnalystReport], client: OpenAI) -> CommanderSummary:
    """The commander's conclusion from every analyst report on one Base."""
    prompt = COMMANDER_PROMPT_TEMPLATE.format(
        history_of_analysts=json.dumps([report.to_dict() for report in reports])
    )
    response = client.responses.create(
        model=COMMANDER_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                ],
            }
        ],
    )

    return CommanderSummary.from_dict(parse_json_reply(response.output_text))
