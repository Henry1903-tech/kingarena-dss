from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ConversionResult:
    converted: int
    revenue: float
    profit: float
    baseline_revenue: float
    baseline_profit: float

    @property
    def delta_revenue(self) -> float:
        return self.revenue - self.baseline_revenue

    @property
    def delta_profit(self) -> float:
        return self.profit - self.baseline_profit


def conversion_model(
    base_count: int,
    base_price: float,
    base_cost: float,
    high_price: float,
    high_cost: float,
    conversion_rate: float,
) -> ConversionResult:
    base_count = max(int(base_count), 0)
    conversion_rate = float(np.clip(conversion_rate, 0.0, 1.0))

    converted = int(round(base_count * conversion_rate))
    remain = base_count - converted

    baseline_revenue = base_count * float(base_price)
    baseline_profit = base_count * (float(base_price) - float(base_cost))

    revenue = remain * float(base_price) + converted * float(high_price)
    profit = remain * (float(base_price) - float(base_cost)) + converted * (float(high_price) - float(high_cost))

    return ConversionResult(
        converted=converted,
        revenue=float(revenue),
        profit=float(profit),
        baseline_revenue=float(baseline_revenue),
        baseline_profit=float(baseline_profit),
    )


@dataclass(frozen=True)
class DiscountSimResult:
    discount_pct: float
    expected_bookings: float
    revenue: float
    profit: float


def discount_fill_profit(
    discount_pct: float,
    baseline_bookings: float,
    baseline_price: float,
    unit_cost: float,
    lift_per_1pct: float,
    marketing_cost_per_1pct: float = 0.0,
) -> DiscountSimResult:
    """
    Assumptions:
    - Bookings increase linearly with discount: bookings = baseline * (1 + lift_per_1pct * discount_pct)
      where discount_pct is in [0, 0.5] (0%..50%).
    - Price decreases: price = baseline_price * (1 - discount_pct)
    - Unit variable cost is constant (unit_cost).
    - Marketing cost increases per booking proportional to discount_pct:
        marketing = bookings * (marketing_cost_per_1pct * (discount_pct*100))
    """
    discount_pct = float(np.clip(discount_pct, 0.0, 0.5))
    baseline_bookings = max(float(baseline_bookings), 0.0)
    baseline_price = max(float(baseline_price), 0.0)
    unit_cost = max(float(unit_cost), 0.0)
    lift_per_1pct = max(float(lift_per_1pct), 0.0)
    marketing_cost_per_1pct = max(float(marketing_cost_per_1pct), 0.0)

    expected_bookings = baseline_bookings * (1.0 + lift_per_1pct * (discount_pct * 100.0))
    price = baseline_price * (1.0 - discount_pct)

    revenue = expected_bookings * price
    treatment_cost = expected_bookings * unit_cost
    marketing_cost = expected_bookings * (marketing_cost_per_1pct * (discount_pct * 100.0))
    profit = revenue - treatment_cost - marketing_cost

    return DiscountSimResult(
        discount_pct=discount_pct,
        expected_bookings=float(expected_bookings),
        revenue=float(revenue),
        profit=float(profit),
    )


@dataclass(frozen=True)
class MaxDiscountResult:
    ok: bool
    discount_pct: float
    best_profit: float
    best_gap: float


def find_max_discount(
    profit_target: float,
    baseline_bookings: float,
    baseline_price: float,
    unit_cost: float,
    lift_per_1pct: float,
    marketing_cost_per_1pct: float = 0.0,
    step_pct: float = 0.5,
) -> MaxDiscountResult:
    """
    Scan 0%..50% to find the maximum discount that still meets profit_target.
    If none meets, return closest to target.
    """
    profit_target = float(profit_target)
    step = max(float(step_pct), 0.1) / 100.0

    best_ok: float | None = None
    best_ok_profit = float("-inf")
    closest_pct: float | None = None
    closest_gap = float("inf")
    closest_profit = float("-inf")

    for d in np.arange(0.0, 0.5000001, step):
        r = discount_fill_profit(
            discount_pct=float(d),
            baseline_bookings=baseline_bookings,
            baseline_price=baseline_price,
            unit_cost=unit_cost,
            lift_per_1pct=lift_per_1pct,
            marketing_cost_per_1pct=marketing_cost_per_1pct,
        )
        gap = abs(r.profit - profit_target)
        if gap < closest_gap:
            closest_gap = gap
            closest_pct = float(d)
            closest_profit = r.profit

        if r.profit >= profit_target:
            best_ok = float(d) if (best_ok is None or d > best_ok) else best_ok
            best_ok_profit = r.profit if d == best_ok else best_ok_profit

    if best_ok is not None:
        return MaxDiscountResult(ok=True, discount_pct=best_ok, best_profit=float(best_ok_profit), best_gap=float(best_ok_profit - profit_target))
    return MaxDiscountResult(ok=False, discount_pct=float(closest_pct or 0.0), best_profit=float(closest_profit), best_gap=float(closest_profit - profit_target))


@dataclass(frozen=True)
class AllocationResult:
    status: str  # ok_lp / ok_greedy / infeasible
    x: dict[str, float]
    total_profit: float
    used_hours: float


def optimize_time_allocation(
    offers: list[tuple[str, float, float, float]],
    total_hours: float,
) -> AllocationResult:
    """
    offers: list of (name, profit_per_unit, hours_per_unit, upper_bound_units)
    Objective: max Σ profit_i * x_i
    Constraints:
      Σ hours_i * x_i <= total_hours
      0 <= x_i <= upper_bound_i
    """
    total_hours = max(float(total_hours), 0.0)
    if not offers or total_hours <= 0:
        return AllocationResult(status="infeasible", x={}, total_profit=0.0, used_hours=0.0)

    names = [o[0] for o in offers]
    profits = np.array([float(o[1]) for o in offers], dtype=float)
    hours = np.array([max(float(o[2]), 1e-9) for o in offers], dtype=float)
    ub = np.array([max(float(o[3]), 0.0) for o in offers], dtype=float)

    # Try LP via SciPy if available
    try:
        from scipy.optimize import linprog  # type: ignore

        c = -profits  # maximize profits -> minimize -profits
        A_ub = [hours.tolist()]
        b_ub = [total_hours]
        bounds = [(0.0, float(ub[i])) for i in range(len(offers))]
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
        if res.success and res.x is not None:
            x = {names[i]: float(res.x[i]) for i in range(len(names))}
            used = float(np.dot(hours, res.x))
            total_profit = float(np.dot(profits, res.x))
            return AllocationResult(status="ok_lp", x=x, total_profit=total_profit, used_hours=used)
    except Exception:  # noqa: BLE001
        pass

    # Greedy heuristic fallback
    score = profits / hours
    order = list(np.argsort(-score))
    remaining = total_hours
    xg = np.zeros(len(offers), dtype=float)
    for i in order:
        if remaining <= 0:
            break
        max_by_time = remaining / hours[i]
        take = min(ub[i], max_by_time)
        if take <= 0:
            continue
        xg[i] = float(take)
        remaining -= float(take * hours[i])

    used = float(np.dot(hours, xg))
    total_profit = float(np.dot(profits, xg))
    return AllocationResult(status="ok_greedy", x={names[i]: float(xg[i]) for i in range(len(names))}, total_profit=total_profit, used_hours=used)

