from src.parser import ParseError, parse_signal
import pytest


SELL = """📌SELL : XAUUSD “SCALP”

FIRST ENTRY : 4389
SECOND ENTRY : 4393

↗️ TP1: 4385
↗️ TP2: 4378
↗️ TP3: 4370
↗️ Tp4 : Trail SL to maximize profits.

‼️SL: 4397 (80 pips)
"""

BUY = """📌BUY : XAUUSD “SCALP”

FIRST ENTRY : 4411
SECOND ENTRY : 4407

↗️ TP1: 4415
↗️ TP2: 4420
↗️ TP3: 4430
↗️ Tp4 : Trail SL to maximize profits.

‼️SL: 4403 (80 pips)
"""

PDF = """XAUUSD • BUY
Entrada 1: 4424 | Entrada 2: 4420
SL: 4416 (80 pips)
TP1: 4428 (+40 pips)
TP2: 4435 (+80 pips)
TP3: 4445 (+230 pips)
TP4: ABIERTO
"""


def test_parse_sell():
    signal = parse_signal(SELL)
    assert signal.direction == "SELL"
    assert signal.symbol == "XAUUSD"
    assert signal.first_entry == 4389
    assert signal.second_entry == 4393
    assert signal.mid_entry == 4391
    assert signal.tp1 == 4385
    assert signal.tp2 == 4378
    assert signal.tp3 == 4370
    assert signal.sl == 4397


def test_parse_buy():
    signal = parse_signal(BUY)
    assert signal.direction == "BUY"
    assert signal.first_entry == 4411
    assert signal.second_entry == 4407
    assert signal.mid_entry == 4409
    assert signal.tp1 == 4415
    assert signal.sl == 4403


def test_parse_pdf_format():
    signal = parse_signal(PDF)
    assert signal.direction == "BUY"
    assert signal.first_entry == 4424
    assert signal.second_entry == 4420
    assert signal.tp3 == 4445
    assert signal.sl == 4416


def test_parse_rejects_garbage():
    with pytest.raises(ParseError):
        parse_signal("hola mercado")
