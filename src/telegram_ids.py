from __future__ import annotations


def channel_candidates(raw: str) -> list:
    value = (raw or "").strip()
    if not value:
        return []
    if not value.lstrip("-").isdigit():
        return [value]
    number = int(value)
    candidates: list[int] = [number]
    if number > 0:
        candidates.append(int(f"-100{number}"))
    elif not str(number).startswith("-100"):
        candidates.append(int(f"-100{abs(number)}"))
    seen: list = []
    for item in candidates:
        if item not in seen:
            seen.append(item)
    return seen
