#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditoria consolidada de Setembro: valida que entradas e saídas no Asaas
batem com entradas e saídas no Advbox.

Usa: TARGET_DATE=2026-09-DD DRY_RUN=true python3 conciliar_v2.py
para cada dia de setembro, consolida e compara totais.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Import das funções do script principal
# (Este script assume que está rodando no mesmo diretório)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from conciliar_v2 import (
        advbox_get_all_transactions,
        asaas_get_financial_transactions_do_dia,
        advbox_get_all_lawsuits,
        identificar_processo_por_referencia,
        TIPOS_RECEITA,
    )
except ImportError as e:
    print(f"Erro ao importar conciliar_v2: {e}")
    sys.exit(1)

TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

def consolidar_setembro():
    """Consolida conciliação de todo o setembro e compara totais."""

    print("\n" + "="*80)
    print("AUDITORIA CONSOLIDADA: SETEMBRO 2026")
    print("Validando entradas e saídas: Asaas ↔ Advbox")
    print("="*80 + "\n")

    # Busca transações do Advbox (uma única vez para o mês todo)
    print("📥 Buscando transações do Advbox... ", end="", flush=True)
    try:
        advbox_txs = advbox_get_all_transactions()
        print(f"OK ({len(advbox_txs)} transações)")
    except Exception as e:
        print(f"ERRO: {e}")
        return None

    # Busca processos do Advbox
    print("📥 Buscando processos do Advbox... ", end="", flush=True)
    try:
        lawsuits = advbox_get_all_lawsuits()
        print(f"OK ({len(lawsuits)} processos)")
    except Exception as e:
        print(f"ERRO: {e}")
        return None

    # Consolida por data
    resultado = {
        "data_auditoria": datetime.now(tz).isoformat(),
        "periodo": "2026-09",
        "dias": {},
        "resumo": {
            "dias_processados": 0,
            "receitas_asaas_total": 0.0,
            "receitas_advbox_total": 0.0,
            "despesas_asaas_total": 0.0,
            "despesas_advbox_total": 0.0,
            "divergencias": [],
        }
    }

    # Processa cada dia de setembro
    print("\n📊 Processando dias de setembro...\n")

    for dia in range(1, 31):
        data = datetime(2026, 9, dia, tzinfo=tz).date()
        data_str = data.isoformat()

        try:
            # Busca receitas do Asaas para esse dia
            asaas_items = asaas_get_financial_transactions_do_dia(data)

            # Filtra receitas do Asaas
            receitas_asaas = [
                i for i in asaas_items
                if i.get("type") in TIPOS_RECEITA and (i.get("value") or 0) > 0
            ]
            valor_receitas_asaas = sum(i.get("value", 0) for i in receitas_asaas)

            # Filtra despesas/taxas do Asaas
            despesas_asaas = [
                i for i in asaas_items
                if i.get("type") not in TIPOS_RECEITA and (i.get("value") or 0) > 0
            ]
            valor_despesas_asaas = sum(i.get("value", 0) for i in despesas_asaas)

            # Filtra transações do Advbox para esse dia
            data_inicio = datetime.combine(data, datetime.min.time()).timestamp()
            data_fim = datetime.combine(data, datetime.max.time()).timestamp()

            txs_dia_advbox = [
                tx for tx in advbox_txs
                if data_inicio <= (tx.get("create_timestamp", 0) or 0) <= data_fim
            ]

            # Separa receitas e despesas no Advbox
            receitas_advbox = [
                tx for tx in txs_dia_advbox
                if (tx.get("type") == "CREDIT" or tx.get("transaction_type") == "input")
                and (tx.get("value") or 0) > 0
            ]
            valor_receitas_advbox = sum(tx.get("value", 0) for tx in receitas_advbox)

            despesas_advbox = [
                tx for tx in txs_dia_advbox
                if (tx.get("type") == "DEBIT" or tx.get("transaction_type") == "output")
                and (tx.get("value") or 0) > 0
            ]
            valor_despesas_advbox = sum(tx.get("value", 0) for tx in despesas_advbox)

            # Registra no resultado
            resultado["dias"][data_str] = {
                "receitas_asaas": len(receitas_asaas),
                "receitas_asaas_valor": valor_receitas_asaas,
                "receitas_advbox": len(receitas_advbox),
                "receitas_advbox_valor": valor_receitas_advbox,
                "despesas_asaas": len(despesas_asaas),
                "despesas_asaas_valor": valor_despesas_asaas,
                "despesas_advbox": len(despesas_advbox),
                "despesas_advbox_valor": valor_despesas_advbox,
                "bate": (
                    abs(valor_receitas_asaas - valor_receitas_advbox) < 0.01
                    and abs(valor_despesas_asaas - valor_despesas_advbox) < 0.01
                )
            }

            # Acumula resumo
            resultado["resumo"]["receitas_asaas_total"] += valor_receitas_asaas
            resultado["resumo"]["receitas_advbox_total"] += valor_receitas_advbox
            resultado["resumo"]["despesas_asaas_total"] += valor_despesas_asaas
            resultado["resumo"]["despesas_advbox_total"] += valor_despesas_advbox

            # Marca divergências
            if not resultado["dias"][data_str]["bate"]:
                resultado["resumo"]["divergencias"].append({
                    "data": data_str,
                    "receitas_diff": abs(valor_receitas_asaas - valor_receitas_advbox),
                    "despesas_diff": abs(valor_despesas_asaas - valor_despesas_advbox),
                })

            resultado["resumo"]["dias_processados"] += 1

            # Print status
            status = "✓" if resultado["dias"][data_str]["bate"] else "✗"
            print(f"{status} 2026-09-{dia:02d}: "
                  f"REC asaas={valor_receitas_asaas:>10.2f} advbox={valor_receitas_advbox:>10.2f} | "
                  f"DESP asaas={valor_despesas_asaas:>10.2f} advbox={valor_despesas_advbox:>10.2f}")

        except Exception as e:
            print(f"✗ 2026-09-{dia:02d}: ERRO - {e}")
            continue

    return resultado


def exibir_relatorio(resultado):
    """Exibe relatório formatado."""
    if not resultado:
        print("Nenhum resultado para exibir.")
        return

    res = resultado["resumo"]

    print("\n" + "="*80)
    print("RESUMO CONSOLIDADO - SETEMBRO 2026")
    print("="*80)
    print(f"\nDias processados: {res['dias_processados']}/30")
    print(f"Divergências encontradas: {len(res['divergencias'])}")

    print("\n📊 ENTRADAS (RECEITAS):")
    print(f"  Asaas:  R$ {res['receitas_asaas_total']:>12,.2f}")
    print(f"  Advbox: R$ {res['receitas_advbox_total']:>12,.2f}")
    diff_rec = abs(res['receitas_asaas_total'] - res['receitas_advbox_total'])
    if diff_rec < 0.01:
        print(f"  Status: ✓ BATE")
    else:
        print(f"  Status: ✗ DIVERGÊNCIA de R$ {diff_rec:,.2f}")

    print("\n📊 SAÍDAS (DESPESAS):")
    print(f"  Asaas:  R$ {res['despesas_asaas_total']:>12,.2f}")
    print(f"  Advbox: R$ {res['despesas_advbox_total']:>12,.2f}")
    diff_desp = abs(res['despesas_asaas_total'] - res['despesas_advbox_total'])
    if diff_desp < 0.01:
        print(f"  Status: ✓ BATE")
    else:
        print(f"  Status: ✗ DIVERGÊNCIA de R$ {diff_desp:,.2f}")

    print("\n📋 FLUXO LÍQUIDO:")
    liquido_asaas = res['receitas_asaas_total'] - res['despesas_asaas_total']
    liquido_advbox = res['receitas_advbox_total'] - res['despesas_advbox_total']
    print(f"  Asaas:  R$ {liquido_asaas:>12,.2f}")
    print(f"  Advbox: R$ {liquido_advbox:>12,.2f}")
    diff_liquido = abs(liquido_asaas - liquido_advbox)
    if diff_liquido < 0.01:
        print(f"  Status: ✓ BATE")
    else:
        print(f"  Status: ✗ DIVERGÊNCIA de R$ {diff_liquido:,.2f}")

    if res['divergencias']:
        print("\n⚠️  DIAS COM DIVERGÊNCIAS:")
        for div in res['divergencias']:
            print(f"  {div['data']}: "
                  f"Receitas Δ R$ {div['receitas_diff']:,.2f} | "
                  f"Despesas Δ R$ {div['despesas_diff']:,.2f}")

    print("\n" + "="*80)


if __name__ == "__main__":
    print("\nℹ️  ATENÇÃO: Este script requer que ADVBOX_TOKEN e ASAAS_TOKEN estejam configurados.")
    print("   Export as variáveis e execute: python3 auditoria_setembro.py\n")

    resultado = consolidar_setembro()
    if resultado:
        exibir_relatorio(resultado)

        # Opcional: salva resultado em JSON para análise
        with open("auditoria_setembro_resultado.json", "w") as f:
            json.dump(resultado, f, indent=2, default=str)
            print(f"\n💾 Resultado salvo em auditoria_setembro_resultado.json")
