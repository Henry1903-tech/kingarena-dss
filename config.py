from __future__ import annotations

from dataclasses import dataclass


APP_TITLE = "King Arena DSS Studio"
APP_ICON = "⚽"

# Excel candidates to auto-load (first existing file wins)
EXCEL_CANDIDATES = (
    "kingarena.xlsx",
    "king_arena.xlsx",
    "data.xlsx",
    "data_mau.xlsx",
    "data mẫu.xlsx",
    "data mẫu(1).xlsx",
    "kingarena_data.xlsx",
    "du_lieu_san",
)


# Basic palette for KPI cards / charts
PALETTE = {
    "revenue": "#2563EB",
    "profit": "#16A34A",
    "due": "#DC2626",
    "discount": "#F59E0B",
    "bookings": "#7C3AED",
    "occupancy": "#0891B2",
}


TIME_SLOT_BINS = (0, 6, 12, 18, 24)
TIME_SLOT_LABELS = ("Đêm", "Sáng", "Chiều", "Tối")


@dataclass(frozen=True)
class DecisionDefaults:
    # Conversion (upsell) defaults
    base_count: int = 1000
    base_price: float = 250_000
    base_cost: float = 120_000
    high_count: int = 0
    high_price: float = 400_000
    high_cost: float = 170_000
    current_conversion_rate: float = 0.12

    # Discount simulator defaults
    baseline_bookings: int = 800
    baseline_price: float = 250_000
    unit_cost: float = 120_000
    lift_per_1pct: float = 0.03  # +3% bookings for each 1% discount (scenario input)
    marketing_cost_per_1pct: float = 2_000  # extra cost per booking per 1% discount
    profit_target: float = 30_000_000

    # Allocation optimizer defaults
    doctor_hours_name: str = "Tổng giờ khả dụng"  # keep naming generic for fields
    total_hours: float = 300.0

    # Service/offer categories for optimizer (profit per hour)
    offers = (
        ("Giờ thấp điểm", 60_000, 1.0, 220.0),
        ("Giờ thường", 90_000, 1.0, 250.0),
        ("Giờ cao điểm", 130_000, 1.0, 180.0),
        ("Combo (nước + áo)", 160_000, 1.0, 90.0),
    )


DEFAULTS = DecisionDefaults()

