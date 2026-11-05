"""Probe the official MOEX CCI dividend feed without treating access errors as zero payouts."""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

ENDPOINT = "https://iss.moex.com/iss/cci/corp-actions/dividends.json"


class DividendSourceUnavailable(RuntimeError):
    pass


def decode_response(raw: bytes) -> dict:
    text = raw.decode("utf-8-sig")
    if text.lstrip().startswith("<"):
        if ("доступна только" in text.lower() and "подписчик" in text.lower()
                or "available only to" in text.lower() and "subscribers" in text.lower()):
            raise DividendSourceUnavailable("SUBSCRIPTION_REQUIRED")
        raise DividendSourceUnavailable("NON_JSON_RESPONSE")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DividendSourceUnavailable("INVALID_JSON_RESPONSE") from exc
    if not isinstance(payload, dict) or not any(
            isinstance(value, dict) and "columns" in value and "data" in value
            for value in payload.values()):
        raise DividendSourceUnavailable("UNEXPECTED_SCHEMA")
    return payload


def fetch_page(start: int = 0, cookie: str | None = None, timeout: int = 15) -> dict:
    url = ENDPOINT + f"?iss.meta=off&start={start}"
    headers = {"Accept": "application/json", "User-Agent": "quant-research/1.0"}
    if cookie:
        headers["Cookie"] = cookie
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return decode_response(response.read())
