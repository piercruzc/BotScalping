from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


Direction = Literal["BUY", "SELL"]
OrderKind = Literal[
    "MARKET",
    "BUY_LIMIT",
    "BUY_STOP",
    "SELL_LIMIT",
    "SELL_STOP",
]
SignalSource = Literal["telegram", "panel", "manager"]
OperatingMode = Literal["demo", "real"]


@dataclass(frozen=True)
class Signal:
    direction: Direction
    symbol: str
    first_entry: float
    second_entry: float
    tp1: float
    tp2: float
    tp3: float
    sl: float
    raw_text: str
    message_id: str = ""

    @property
    def mid_entry(self) -> float:
        return (self.first_entry + self.second_entry) / 2.0


@dataclass
class Tick:
    bid: float
    ask: float

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass
class PlannedOrder:
    leg: int
    side: Direction
    kind: OrderKind
    entry: float
    sl: float
    tp: Optional[float]
    volume: float
    skip_reason: Optional[str] = None

    @property
    def accepted(self) -> bool:
        return self.skip_reason is None


@dataclass
class PlanResult:
    signal: Signal
    orders: list[PlannedOrder] = field(default_factory=list)
    rejected: Optional[str] = None

    @property
    def accepted_orders(self) -> list[PlannedOrder]:
        return [order for order in self.orders if order.accepted]


@dataclass
class AccountSnapshot:
    connected: bool
    login: int = 0
    server: str = ""
    name: str = ""
    balance: float = 0.0
    equity: float = 0.0
    is_demo: bool = True
    trade_mode: str = "unknown"
    error: str = ""


@dataclass
class PositionSnapshot:
    ticket: int
    symbol: str
    side: Direction
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    comment: str
    magic: int


@dataclass
class PendingSnapshot:
    ticket: int
    symbol: str
    kind: str
    volume: float
    price: float
    sl: float
    tp: float
    comment: str
    magic: int


@dataclass
class ExecutionReport:
    dry_run: bool
    source: SignalSource
    rejected: Optional[str]
    placed: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
