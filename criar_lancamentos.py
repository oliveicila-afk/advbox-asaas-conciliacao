#!/usr/bin/env python3
"""Aplica o plano de conciliação recém-gerado, sem usar relatórios antigos."""

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conciliar_v2 import (
    DRY_RUN,
    TAXAS_DIARIAS_CONSOLIDADAS,
    TIPOS_ESTORNO,
    TIPOS_IGNORAR_INFORMATIVO,
    TIPOS_RECEITA,
    TIPO_TAXA_BANCARIA_CLIENTE,
    advbox_get_all_lawsuits,
    advbox_get_all_transactions,
    advbox_put,
    asaas_get_financial_transactions_do_dia,
    aplicar_correcoes,
    categoria_por_tese,
    categoria_repasse_cliente,
    enriquecer_receita_faltando_com_processo,
    montar_relatorio,
    resolver_categoria_id,
    resolver_centro_custo_id,
)
from period_reconciliation import plan_daily_movements


ANALYSIS_FILE = Path(os.environ.get("ANALYSIS_FILE", "analysis_report.json"))
HANDLED_MISSING_TYPES = (
    set(TIPOS_RECEITA)
    | set(TAXAS_DIARIAS_CONSOLIDADAS)
)


def load_analysis(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Plano atual não encontrado: {path}. Execute analise_por_data_valor.py primeiro."
        )
    analysis = json.loads(path.read_text(encoding="utf-8"))
    if analysis.get("schema_version") != 1 or not isinstance(analysis.get("days"), list):
        raise ValueError(f"Formato inválido no plano de conciliação: {path}")
    if not analysis["days"]:
        raise ValueError("O plano de conciliação não contém dias para processar.")
    return analysis


def _item_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("transactions_id")
    return str(value) if value is not None else None


def _filter_report_to_missing_movements(
    report: dict[str, Any], missing_movements: list[dict[str, Any]]
) -> None:
    missing_ids = {_item_id(item) for item in missing_movements}
    missing_ids.discard(None)

    def is_missing(item: dict[str, Any]) -> bool:
        item_id = _item_id(item)
        if item_id is not None:
            return item_id in missing_ids
        return any(item == missing for missing in missing_movements)

    report["receita_faltando"] = [
        item for item in report.get("receita_faltando", []) if is_missing(item)
    ]
    report["taxa_bancaria_faltando"] = [
        item for item in report.get("taxa_bancaria_faltando", []) if is_missing(item)
    ]


def _preflight_report(report: dict[str, Any]) -> list[str]:
    errors = []
    for receita in report.get("receita_faltando", []):
        processo = receita.get("_processo_identificado")
        if not processo:
            errors.append(f"Receita Asaas {_item_id(receita) or '<sem ID>'}: sem processo identificado.")
            continue

        categoria_id = None
        if processo.get("confianca_categoria") == "precedente":
            categoria_id = resolver_categoria_id(processo.get("categoria_final"))
        if not categoria_id and processo.get("tipo_honorario") and processo.get("tese"):
            categoria_id, _ = categoria_por_tese(
                processo["tipo_honorario"],
                processo["tese"],
            )

        centro_custo_id = resolver_centro_custo_id(processo.get("centro_custo_sugerido"))
        protocolo = processo.get("protocolo") or {}
        valor = float(receita.get("value", 0) or 0)
        valor_creditado = protocolo.get("valor_creditado")
        if valor_creditado is not None and abs(float(valor_creditado) - valor) > 0.02:
            errors.append(f"Receita Asaas {_item_id(receita) or '<sem ID>'}: valor não confere com o protocolo.")
        elif not categoria_id or not centro_custo_id:
            errors.append(f"Receita Asaas {_item_id(receita) or '<sem ID>'}: categoria/centro de custo não resolvido.")

        repasse = float(protocolo.get("repasse_cliente") or 0)
        if repasse > 0.01 and not categoria_repasse_cliente(processo.get("tese"))[0]:
            errors.append(f"Receita Asaas {_item_id(receita) or '<sem ID>'}: categoria do repasse não resolvida.")

    for info in report.get("taxas_diarias_info", {}).values():
        if info.get("faltando", 0) > 0.01:
            if not resolver_categoria_id(info.get("nome")):
                errors.append(f"Categoria {info.get('nome')} não encontrada em /settings.")
            if not resolver_centro_custo_id("DESPESAS FINANCEIRAS GERAL"):
                errors.append("Centro de custo DESPESAS FINANCEIRAS GERAL não encontrado em /settings.")
    return errors


def _preflight_analysis(analysis: dict[str, Any]) -> list[str]:
    errors = []
    for day in analysis["days"]:
        movements = day.get("movements") or {}
        target_date = day.get("data", "<sem data>")
        if not movements.get("safe_to_mutate"):
            errors.append(
                f"{target_date}: movimentação sem classificação segura "
                f"(ASAAS={movements.get('unsupported_asaas_types', [])}, "
                f"AdvBox={len(movements.get('unsupported_advbox_ids', [] ) or [])}, "
                f"excessos de categoria={len(movements.get('daily_category_overages', [] ) or [])})."
            )
            continue

        unhandled = [
            item.get("type") or "<sem tipo>"
            for item in movements.get("asaas_faltando", [])
            if item.get("type") not in HANDLED_MISSING_TYPES
        ]
        if unhandled:
            errors.append(f"{target_date}: tipos sem regra de inclusão automática: {sorted(set(unhandled))}.")

    return errors


def _delete_phantoms(day: dict[str, Any]) -> tuple[int, list[str]]:
    deleted = 0
    errors = []
    for item in (day.get("movements") or {}).get("advbox_fantasmas", []):
        transaction_id = _item_id(item)
        if transaction_id is None:
            errors.append(f"{day['data']}: lançamento excedente sem ID.")
            continue
        if advbox_put(transaction_id, {"status": "deleted"}):
            deleted += 1
        else:
            errors.append(f"{day['data']}: não foi possível excluir o lançamento AdvBox {transaction_id}.")
    return deleted, errors


def _verify(analysis: dict[str, Any]) -> list[str]:
    advbox_items = advbox_get_all_transactions()
    errors = []
    for day in analysis["days"]:
        target_date = day["data"]
        asaas_items = asaas_get_financial_transactions_do_dia(target_date)
        report = montar_relatorio(target_date, advbox_items, asaas_items)
        advbox_day = [
            item for item in advbox_items
            if item.get("date_payment") == target_date
        ]
        movements = plan_daily_movements(
            asaas_items,
            advbox_day,
            target_date,
            income_types=set(TIPOS_RECEITA),
            expense_types=set(TIPOS_ESTORNO) | set(TAXAS_DIARIAS_CONSOLIDADAS) | {TIPO_TAXA_BANCARIA_CLIENTE},
            ignored_types=set(TIPOS_IGNORAR_INFORMATIVO),
            consolidated_expense_categories={
                transaction_type: metadata["nome"]
                for transaction_type, metadata in TAXAS_DIARIAS_CONSOLIDADAS.items()
            },
        )
        _filter_report_to_missing_movements(report, movements["asaas_faltando"])
        unresolved = (
            len(movements["asaas_faltando"])
            + len(movements["advbox_fantasmas"])
            + len(report.get("receita_faltando", []))
            + len(report.get("taxa_bancaria_faltando", []))
            + len(report.get("receita_data_errada", []))
            + len(report.get("taxa_bancaria_data_errada", []))
            + sum(info.get("faltando", 0) > 0.01 for info in report.get("taxas_diarias_info", {}).values())
        )
        totals_differ = (
            movements["expected_income_cents"] != movements["actual_income_cents"]
            or movements["expected_expense_cents"] != movements["actual_expense_cents"]
        )
        if not movements["safe_to_mutate"] or unresolved or totals_differ:
            errors.append(
                f"{target_date}: ainda há divergências após a conciliação "
                f"(receitas {movements['actual_income_cents']}/{movements['expected_income_cents']} "
                f"centavos; despesas {movements['actual_expense_cents']}/"
                f"{movements['expected_expense_cents']} centavos; itens pendentes={unresolved})."
            )
    return errors


def main() -> int:
    if not os.environ.get("ADVBOX_TOKEN") or not os.environ.get("ASAAS_TOKEN"):
        raise RuntimeError("ADVBOX_TOKEN e ASAAS_TOKEN precisam estar configurados.")

    analysis = load_analysis(ANALYSIS_FILE)
    preflight_errors = _preflight_analysis(analysis)
    if preflight_errors:
        for error in preflight_errors:
            print(f"PENDENTE: {error}")
        print("Nenhuma alteração foi enviada ao AdvBox.")
        return 1

    for day in analysis["days"]:
        _filter_report_to_missing_movements(
            day["report"],
            (day.get("movements") or {}).get("asaas_faltando", []),
        )

    if any(day["report"].get("receita_faltando") for day in analysis["days"]):
        lawsuits = advbox_get_all_lawsuits()
        advbox_items = advbox_get_all_transactions()
        for day in analysis["days"]:
            report = day["report"]
            if report.get("receita_faltando"):
                enrich_receita_faltando_com_processo(
                    report,
                    lawsuits,
                    advbox_items,
                )

    for day in analysis["days"]:
        errors = _preflight_report(day["report"])
        if errors:
            for error in errors:
                print(f"PENDENTE: {day['data']}: {error}")
            print("Nenhuma alteração foi enviada ao AdvBox.")
            return 1

    created_or_corrected = 0
    deleted = 0
    operation_errors = []
    for day in analysis["days"]:
        result = aplicar_correcoes(day["report"])
        created_or_corrected += len(result["aplicadas"])
        if result["falhas"]:
            operation_errors.append(f"{day['data']}: {len(result['falhas'])} operação(ões) falharam.")
        if result.get("pendentes"):
            operation_errors.append(f"{day['data']}: {len(result['pendentes'])} movimentação(ões) sem regra automática.")

    if operation_errors:
        for error in operation_errors:
            print(f"ERRO: {error}")
        return 1

    for day in analysis["days"]:
        count, delete_errors = _delete_phantoms(day)
        deleted += count
        operation_errors.extend(delete_errors)

    if operation_errors:
        for error in operation_errors:
            print(f"ERRO: {error}")
        return 1

    if DRY_RUN:
        print(
            f"SIMULAÇÃO concluída: {created_or_corrected} inclusão(ões)/correção(ões) "
            f"e {deleted} exclusão(ões) seriam enviadas ao AdvBox."
        )
        return 0

    verification_errors = _verify(analysis)
    if verification_errors:
        for error in verification_errors:
            print(f"DIVERGÊNCIA: {error}")
        return 1

    print(
        f"Conciliação verificada: {created_or_corrected} inclusão(ões)/correção(ões) "
        f"e {deleted} exclusão(ões) no AdvBox."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
