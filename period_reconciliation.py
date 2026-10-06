from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata
from typing import Any


def date_range(start_date: str, end_date: str) -> list[str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("END_DATE must be on or after START_DATE")

    dates = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def _cents(value: Any) -> int:
    text = str(value or 0).strip()
    text = re.sub(r"[^\d,.\-+]", "", text)
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return int((Decimal(text) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid transaction amount: {value!r}") from exc


def _normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().upper())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _advbox_direction(item: dict[str, Any]) -> str | None:
    entry_type = str(item.get("entry_type") or "").strip().lower()
    if entry_type in {"income", "credit"}:
        return "income"
    if entry_type in {"expense", "debit"}:
        return "expense"
    return None


def plan_daily_movements(
    asaas_items: list[dict[str, Any]],
    advbox_items: list[dict[str, Any]],
    target_date: str,
    *,
    income_types: set[str],
    expense_types: set[str],
    ignored_types: set[str],
    consolidated_expense_categories: dict[str, str],
    excluded_advbox_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Match posted movements by date, direction and cents, preserving duplicates."""
    excluded_ids = excluded_advbox_ids or set()
    expected: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    actual: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    expected_daily_fees: dict[str, int] = defaultdict(int)
    actual_daily_fees: dict[str, int] = defaultdict(int)
    unsupported_types: set[str] = set()
    unsupported_advbox_ids: list[str] = []

    normalized_consolidated_categories = {
        transaction_type: _normalize_label(category)
        for transaction_type, category in consolidated_expense_categories.items()
    }

    for item in asaas_items:
        if item.get("date") != target_date:
            continue
        transaction_type = str(item.get("type") or "")
        if transaction_type in ignored_types:
            continue
        amount = abs(_cents(item.get("value", 0)))
        if transaction_type in normalized_consolidated_categories:
            category = normalized_consolidated_categories[transaction_type]
            expected_daily_fees[category] += amount
            continue
        if transaction_type in income_types:
            direction = "income"
        elif transaction_type in expense_types:
            direction = "expense"
        else:
            unsupported_types.add(transaction_type or "<missing type>")
            continue
        expected[(direction, amount)].append(item)

    for item in advbox_items:
        if item.get("date_payment") != target_date:
            continue
        transaction_id = item.get("id") or item.get("transactions_id")
        if transaction_id is not None and str(transaction_id) in excluded_ids:
            continue

        category = _normalize_label(str(item.get("category") or ""))
        if category in set(normalized_consolidated_categories.values()):
            actual_daily_fees[category] += abs(_cents(item.get("amount", 0)))
            continue

        direction = _advbox_direction(item)
        if direction is None:
            unsupported_advbox_ids.append(str(transaction_id or "<missing id>"))
            continue
        actual[(direction, abs(_cents(item.get("amount", 0))))].append(item)

    daily_category_overages = []
    for category, amount in actual_daily_fees.items():
        expected_amount = expected_daily_fees.get(category, 0)
        if amount > expected_amount:
            daily_category_overages.append({
                "category": category,
                "expected_cents": expected_amount,
                "actual_cents": amount,
            })

    unsupported = bool(unsupported_types or unsupported_advbox_ids or daily_category_overages)
    missing_asaas = []
    advbox_only = []
    keys = set(expected) | set(actual)
    for key in sorted(keys):
        asaas_rows = expected.get(key, [])
        advbox_rows = actual.get(key, [])
        paired = min(len(asaas_rows), len(advbox_rows))
        missing_asaas.extend(asaas_rows[paired:])
        advbox_only.extend(advbox_rows[paired:])

    return {
        "data": target_date,
        "safe_to_mutate": not unsupported,
        "unsupported_asaas_types": sorted(unsupported_types),
        "unsupported_advbox_ids": unsupported_advbox_ids,
        "daily_category_overages": daily_category_overages,
        "expected_income_cents": sum(amount * len(rows) for (direction, amount), rows in expected.items() if direction == "income"),
        "actual_income_cents": sum(amount * len(rows) for (direction, amount), rows in actual.items() if direction == "income"),
        "expected_expense_cents": sum(expected_daily_fees.values()) + sum(
            amount * len(rows) for (direction, amount), rows in expected.items() if direction == "expense"
        ),
        "actual_expense_cents": sum(actual_daily_fees.values()) + sum(
            amount * len(rows) for (direction, amount), rows in actual.items() if direction == "expense"
        ),
        "asaas_faltando": missing_asaas,
        "advbox_fantasmas": [] if unsupported else advbox_only,
    }
