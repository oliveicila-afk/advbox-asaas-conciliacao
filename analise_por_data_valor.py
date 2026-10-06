#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o plano atual de conciliação diária para um intervalo de datas."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conciliar_v2 import (
    TAXAS_DIARIAS_CONSOLIDADAS,
    TIPOS_ESTORNO,
    TIPOS_IGNORAR_INFORMATIVO,
    TIPOS_RECEITA,
    TIPO_TAXA_BANCARIA_CLIENTE,
    advbox_get_all_transactions,
    asaas_get_financial_transactions_do_dia,
    montar_relatorio,
)
from period_reconciliation import date_range, plan_daily_movements


def main() -> int:
    if not os.environ.get("ADVBOX_TOKEN") or not os.environ.get("ASAAS_TOKEN"):
        raise RuntimeError("ADVBOX_TOKEN e ASAAS_TOKEN precisam estar configurados.")

    dates = date_range(
        os.environ.get("START_DATE") or "2026-09-01",
        os.environ.get("END_DATE") or "2026-09-10",
    )
    advbox_items = advbox_get_all_transactions()
    advbox_period = [
        item for item in advbox_items
        if dates[0] <= str(item.get("date_payment") or "") <= dates[-1]
    ]
    reports = []

    for target_date in dates:
        asaas_items = asaas_get_financial_transactions_do_dia(target_date)
        advbox_day = [
            item for item in advbox_period
            if item.get("date_payment") == target_date
        ]
        report = montar_relatorio(target_date, advbox_period, asaas_items)
        reports.append({
            "data": target_date,
            "asaas_items": asaas_items,
            "advbox_items": advbox_day,
            "report": report,
        })

    wrong_date_ids = {
        str(item.get("advbox", {}).get("id") or item.get("advbox", {}).get("transactions_id"))
        for day in reports
        for key in ("receita_data_errada", "taxa_bancaria_data_errada")
        for item in day["report"].get(key, [])
        if item.get("advbox", {}).get("id") or item.get("advbox", {}).get("transactions_id")
    }
    income_types = set(TIPOS_RECEITA)
    expense_types = set(TIPOS_ESTORNO) | {TIPO_TAXA_BANCARIA_CLIENTE}
    daily_fee_types = {
        transaction_type: metadata["nome"]
        for transaction_type, metadata in TAXAS_DIARIAS_CONSOLIDADAS.items()
    }
    ignored_types = set(TIPOS_IGNORAR_INFORMATIVO)

    for day in reports:
        plan = plan_daily_movements(
            day["asaas_items"],
            day["advbox_items"],
            day["data"],
            income_types=income_types,
            expense_types=expense_types,
            ignored_types=ignored_types,
            consolidated_expense_categories=daily_fee_types,
            excluded_advbox_ids=wrong_date_ids,
        )
        day["movements"] = plan
        print(
            f"{day['data']}: receitas Asaas={plan['expected_income_cents'] / 100:.2f}, "
            f"AdvBox={plan['actual_income_cents'] / 100:.2f}; despesas "
            f"Asaas={plan['expected_expense_cents'] / 100:.2f}, "
            f"AdvBox={plan['actual_expense_cents'] / 100:.2f}; "
            f"faltantes={len(plan['asaas_faltando'])}, "
            f"extras={len(plan['advbox_fantasmas'])}, "
            f"seguro={plan['safe_to_mutate']}"
        )

    output_path = Path(os.environ.get("ANALYSIS_FILE", "analysis_report.json"))
    output_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "start_date": dates[0],
                "end_date": dates[-1],
                "days": reports,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Plano de conciliação gravado em {output_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
