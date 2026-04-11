from __future__ import annotations

import json
import re
import requests
from typing import Any, Protocol


class PreferenceParser(Protocol):
    version: str

    def parse(self, raw_text: str, timezone_name: str) -> dict[str, Any]:
        ...


class StubPreferenceParser:
    version = "stub-v1"

    def parse(self, raw_text: str, timezone_name: str) -> dict[str, Any]:
        text = raw_text.lower()
        preferred_weekdays: list[str] = []
        disallowed_weekdays: list[str] = []

        weekday_map = {
            "monday": "MON",
            "mon": "MON",
            "tuesday": "TUE",
            "tue": "TUE",
            "wednesday": "WED",
            "wed": "WED",
            "thursday": "THU",
            "thu": "THU",
            "friday": "FRI",
            "fri": "FRI",
            "saturday": "SAT",
            "sat": "SAT",
            "sunday": "SUN",
            "sun": "SUN",
        }

        for token, weekday in weekday_map.items():
            if token not in text:
                continue
            if any(prefix in text for prefix in (f"not {token}", f"avoid {token}", f"no {token}")):
                if weekday not in disallowed_weekdays:
                    disallowed_weekdays.append(weekday)
            elif weekday not in preferred_weekdays:
                preferred_weekdays.append(weekday)

        preferred_time_ranges: list[dict[str, Any]] = []
        disallowed_time_ranges: list[dict[str, Any]] = []

        if "morning" in text:
            preferred_time_ranges.append({"start_local": "09:00", "end_local": "12:00", "weight": 1.0})
        if "afternoon" in text:
            preferred_time_ranges.append({"start_local": "13:00", "end_local": "17:00", "weight": 1.0})
        if "evening" in text:
            preferred_time_ranges.append({"start_local": "17:00", "end_local": "20:00", "weight": 1.0})

        not_before_match = re.search(r"not before (\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
        if not_before_match:
            disallowed_time_ranges.append(
                {"start_local": "00:00", "end_local": _normalize_hour_match(not_before_match), "weight": 1.0}
            )

        not_after_match = re.search(r"not after (\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
        if not_after_match:
            disallowed_time_ranges.append(
                {"start_local": _normalize_hour_match(not_after_match), "end_local": "23:59", "weight": 1.0}
            )

        return {
            "schema_version": "1.0",
            "timezone": timezone_name,
            "preferred_weekdays": preferred_weekdays,
            "disallowed_weekdays": disallowed_weekdays,
            "preferred_time_ranges": preferred_time_ranges,
            "disallowed_time_ranges": disallowed_time_ranges,
            "notes": raw_text.strip() or None,
        }


class FeatherPreferenceParser:
    version = "feather-v1"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.url = "https://api.feather.ai/v1/chat/completions"

    def parse(self, raw_text: str, timezone_name: str) -> dict[str, Any]:
        requests = _get_requests_module()

        prompt = f"""
Convert the following scheduling preferences into valid JSON.

Return ONLY JSON with this exact shape:
{{
  "schema_version": "1.0",
  "timezone": "{timezone_name}",
  "preferred_weekdays": ["MON"],
  "disallowed_weekdays": ["FRI"],
  "preferred_time_ranges": [{{"start_local": "09:00", "end_local": "12:00", "weight": 1.0}}],
  "disallowed_time_ranges": [{{"start_local": "00:00", "end_local": "09:00", "weight": 1.0}}],
  "notes": "short summary"
}}

Allowed weekday values are MON, TUE, WED, THU, FRI, SAT, SUN.
Time values must be HH:MM in 24-hour format.
If a field is unknown, return an empty list or null.

Input:
"{raw_text}"
"""

        response = requests.post(
            self.url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            timeout=30,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.removeprefix("```json").removeprefix("```").strip()
            if content.endswith("```"):
                content = content[:-3].strip()

        raw_structured = json.loads(content)
        return _coerce_structured_output(raw_structured=raw_structured, timezone_name=timezone_name, raw_text=raw_text)


class GroqPreferenceParser:
    version = "groq-v1"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"

    def parse(self, raw_text: str, timezone_name: str) -> dict[str, Any]:
        system_prompt = """You are a scheduling assistant that converts natural language availability preferences into structured JSON constraints. You must return ONLY valid JSON with no explanation, no markdown, no code fences, no preamble. The JSON must exactly match this schema:

{
  "schema_version": "1.0",
  "timezone": "<the user timezone passed in>",
  "preferred_weekdays": ["MON"],
  "disallowed_weekdays": ["FRI"],
  "preferred_time_ranges": [{"start_local": "09:00", "end_local": "12:00", "weight": 1.0}],
  "disallowed_time_ranges": [{"start_local": "00:00", "end_local": "09:00", "weight": 1.0}],
  "notes": "brief summary of what the user said"
}

Rules:
- Allowed weekday values are exactly: MON, TUE, WED, THU, FRI, SAT, SUN
- Time values must be HH:MM in 24-hour format
- A weekday cannot appear in both preferred_weekdays and disallowed_weekdays
- If a field has no relevant information, return an empty list
- notes should be a short plain English summary of the constraints you extracted
- Return ONLY the JSON object. No explanation. No markdown. No code blocks."""
        user_prompt = f'User timezone: {timezone_name}\nUser preference text: "{raw_text}"'

        try:
            response = requests.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                    "max_tokens": 512,
                },
                timeout=30,
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.removeprefix("```json").removeprefix("```").strip()
                if content.endswith("```"):
                    content = content[:-3].strip()

            raw_structured = json.loads(content)
            return _coerce_structured_output(
                raw_structured=raw_structured,
                timezone_name=timezone_name,
                raw_text=raw_text,
            )
        except Exception as exc:  # noqa: BLE001 - provider and JSON errors should surface as ValueError
            raise ValueError(f"Groq parser failed: {exc}") from exc


def build_preference_parser(mode: str, api_key: str = "") -> PreferenceParser:
    if mode == "groq":
        if not api_key:
            raise ValueError("GROQ_API_KEY is required when PARSER_MODE=groq")
        return GroqPreferenceParser(api_key=api_key)
    if mode == "feather":
        if not api_key:
            raise ValueError("FEATHER_API_KEY is required when PARSER_MODE=feather")
        return FeatherPreferenceParser(api_key=api_key)
    return StubPreferenceParser()


def _get_requests_module():
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("requests must be installed to use live HTTP integrations") from exc
    return requests


def _normalize_hour_match(match: re.Match[str]) -> str:
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _coerce_structured_output(raw_structured: dict[str, Any], timezone_name: str, raw_text: str) -> dict[str, Any]:
    preferred_weekdays = [_normalize_weekday(item) for item in raw_structured.get("preferred_weekdays", [])]
    disallowed_weekdays = [_normalize_weekday(item) for item in raw_structured.get("disallowed_weekdays", [])]

    return {
        "schema_version": str(raw_structured.get("schema_version") or "1.0"),
        "timezone": str(raw_structured.get("timezone") or timezone_name),
        "preferred_weekdays": [item for item in preferred_weekdays if item],
        "disallowed_weekdays": [item for item in disallowed_weekdays if item],
        "preferred_time_ranges": _normalize_ranges(raw_structured.get("preferred_time_ranges", [])),
        "disallowed_time_ranges": _normalize_ranges(raw_structured.get("disallowed_time_ranges", [])),
        "notes": _normalize_notes(raw_structured.get("notes"), raw_text=raw_text),
    }


def _normalize_weekday(value: Any) -> str | None:
    if not value:
        return None
    token = str(value).strip().upper()[:3]
    valid = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
    return token if token in valid else None


def _normalize_ranges(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        start_value = item.get("start_local") or item.get("start")
        end_value = item.get("end_local") or item.get("end")
        if not start_value or not end_value:
            continue
        normalized.append(
            {
                "start_local": str(start_value),
                "end_local": str(end_value),
                "weight": float(item.get("weight", 1.0)),
            }
        )
    return normalized


def _normalize_notes(value: Any, raw_text: str) -> str | None:
    if value is None:
        return raw_text.strip() or None
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return "; ".join(items) or (raw_text.strip() or None)
    return str(value).strip() or (raw_text.strip() or None)
