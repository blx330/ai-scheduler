from __future__ import annotations

import json
import re
from typing import Any, Protocol

from app.domain.preferences.models import CachedPracticePreference, summarize_cached_preference

GROQ_PROFILE_MODEL = "llama3-8b-8192"


class UserProfilePreferenceParser(Protocol):
    version: str

    def parse(self, raw_text: str, timezone_name: str) -> dict[str, Any]:
        ...


class StubUserProfilePreferenceParser:
    version = "stub-profile-v1"

    def parse(self, raw_text: str, timezone_name: str) -> dict[str, Any]:
        text = raw_text.lower()
        preferred_days: list[str] = []
        avoid_days: list[str] = []

        if "weekend" in text:
            preferred_days.extend(["Saturday", "Sunday"])
        if "weekday" in text:
            preferred_days.extend(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])

        for day_name in DAY_NAMES:
            lowered = day_name.lower()
            pattern = rf"\b{lowered}s?\b"
            if not re.search(pattern, text):
                continue
            if re.search(rf"\b(?:avoid|no|not|never)\s+{lowered}s?\b", text):
                if day_name not in avoid_days:
                    avoid_days.append(day_name)
                continue
            if day_name not in preferred_days:
                preferred_days.append(day_name)

        earliest_time = _extract_time(
            text,
            [
                r"(?:not before|never before|no earlier than|earliest(?: time)?|after)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            ],
        )
        latest_time = _extract_time(
            text,
            [
                r"(?:not after|no later than|latest(?: time)?|before|by)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            ],
        )

        if "mornings only" in text or "morning only" in text:
            latest_time = latest_time or "12:00"

        payload = CachedPracticePreference(
            preferred_days=preferred_days,
            avoid_days=avoid_days,
            earliest_time=earliest_time,
            latest_time=latest_time,
            notes=raw_text.strip() or None,
        )
        return payload.model_dump(mode="json") | {"summary": summarize_cached_preference(payload)}


class GroqUserProfilePreferenceParser:
    version = "groq-profile-v1"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.model = GROQ_PROFILE_MODEL

    def parse(self, raw_text: str, timezone_name: str) -> dict[str, Any]:
        groq_client_class = _get_groq_client_class()
        client = groq_client_class(api_key=self.api_key)
        system_prompt = """You convert dance practice preference text into strict JSON.

Return ONLY a JSON object with this exact shape:
{
  "preferred_days": ["Saturday", "Sunday"],
  "avoid_days": ["Friday"],
  "earliest_time": "09:00",
  "latest_time": "12:00",
  "notes": "weekends strongly preferred",
  "summary": "prefers weekends, avoids Fridays, never before 9:00 AM"
}

Rules:
- Allowed day values are full English weekday names only.
- earliest_time and latest_time must be HH:MM in 24-hour format or null.
- If you are unsure, leave fields empty or null instead of guessing.
- summary must be a short plain-English summary.
- Return JSON only with no markdown or commentary."""
        completion = client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=400,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": (
                        f"User timezone: {timezone_name}\n"
                        f'User preference text: "{raw_text}"'
                    ),
                },
            ],
        )
        content = (completion.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = content.removeprefix("```json").removeprefix("```").strip()
            if content.endswith("```"):
                content = content[:-3].strip()
        raw_structured = json.loads(content)
        return _coerce_profile_output(raw_structured, raw_text=raw_text)


def build_user_profile_preference_parser(api_key: str = "") -> UserProfilePreferenceParser:
    if api_key:
        return GroqUserProfilePreferenceParser(api_key=api_key)
    return StubUserProfilePreferenceParser()


def _get_groq_client_class():
    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError("groq must be installed to use Groq preference parsing") from exc
    return Groq


def _coerce_profile_output(raw_structured: dict[str, Any], raw_text: str) -> dict[str, Any]:
    payload = CachedPracticePreference(
        preferred_days=raw_structured.get("preferred_days", []),
        avoid_days=raw_structured.get("avoid_days", []),
        earliest_time=_normalize_time_value(raw_structured.get("earliest_time")),
        latest_time=_normalize_time_value(raw_structured.get("latest_time")),
        notes=_normalize_text(raw_structured.get("notes")) or (raw_text.strip() or None),
        summary=_normalize_text(raw_structured.get("summary")),
    )
    summary = payload.summary_text()
    return payload.model_dump(mode="json") | {"summary": summary}


def _extract_time(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _normalize_time_value(match.group(1))
    return None


def _normalize_time_value(value: Any) -> str | None:
    if value is None:
        return None
    token = str(value).strip().lower()
    if not token:
        return None

    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", token)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
