from __future__ import annotations

import re
import unicodedata

from .models import Signal


_NUMBER = r"([0-9]+(?:[.,][0-9]+)?)"

_DIRECTION = re.compile(r"\b(BUY|SELL|COMPRA|VENTA)\b", re.IGNORECASE)
_SYMBOL = re.compile(r"\b(XAUUSD|GOLD|XAUUSDM)\b", re.IGNORECASE)
_FIRST = re.compile(
    rf"(?:FIRST\s*ENTRY|ENTRADA\s*1|ENTRY\s*1)\s*[:|]?\s*{_NUMBER}",
    re.IGNORECASE,
)
_SECOND = re.compile(
    rf"(?:SECOND\s*ENTRY|ENTRADA\s*2|ENTRY\s*2)\s*[:|]?\s*{_NUMBER}",
    re.IGNORECASE,
)
_TP = {
    1: re.compile(rf"TP\s*1\s*[:|]?\s*{_NUMBER}", re.IGNORECASE),
    2: re.compile(rf"TP\s*2\s*[:|]?\s*{_NUMBER}", re.IGNORECASE),
    3: re.compile(rf"TP\s*3\s*[:|]?\s*{_NUMBER}", re.IGNORECASE),
}
_SL = re.compile(rf"(?:‼️)?\s*SL\s*[:|]?\s*{_NUMBER}", re.IGNORECASE)


class ParseError(ValueError):
    pass


def parse_signal(text: str, message_id: str = "") -> Signal:
    if not text or not text.strip():
        raise ParseError("Mensaje vacío")

    normalized = _normalize(text)
    direction_match = _DIRECTION.search(normalized)
    if not direction_match:
        raise ParseError("No se encontró BUY o SELL")

    raw_direction = direction_match.group(1).upper()
    direction = {
        "BUY": "BUY",
        "COMPRA": "BUY",
        "SELL": "SELL",
        "VENTA": "SELL",
    }[raw_direction]

    symbol_match = _SYMBOL.search(normalized)
    symbol = symbol_match.group(1).upper() if symbol_match else "XAUUSD"
    if symbol == "GOLD":
        symbol = "XAUUSD"

    first = _require(_FIRST.search(normalized), "FIRST ENTRY / Entrada 1")
    second = _require(_SECOND.search(normalized), "SECOND ENTRY / Entrada 2")
    tp1 = _require(_TP[1].search(normalized), "TP1")
    tp2 = _require(_TP[2].search(normalized), "TP2")
    tp3 = _require(_TP[3].search(normalized), "TP3")
    sl = _require(_SL.search(normalized), "SL")

    return Signal(
        direction=direction,  # type: ignore[arg-type]
        symbol=symbol,
        first_entry=_to_float(first.group(1)),
        second_entry=_to_float(second.group(1)),
        tp1=_to_float(tp1.group(1)),
        tp2=_to_float(tp2.group(1)),
        tp3=_to_float(tp3.group(1)),
        sl=_to_float(sl.group(1)),
        raw_text=text,
        message_id=str(message_id or ""),
    )


def _normalize(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'")
    cleaned = cleaned.replace("•", " ").replace("|", " | ")
    return cleaned


def _require(match: re.Match[str] | None, label: str) -> re.Match[str]:
    if match is None:
        raise ParseError(f"No se encontró {label}")
    return match


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "."))
