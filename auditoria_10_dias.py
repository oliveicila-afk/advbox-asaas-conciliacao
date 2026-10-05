#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditoria rápida: primeiros 10 dias de setembro.
Valida se Asaas ↔ Advbox batem (sim/não) e aponta divergências.
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from conciliar_v2 import (
        advbox_get_all_transactions,
        asaas_get_financial_transactions_do_dia,
        TIPOS_RECEITA,
    )
except ImportError as e:
    print(f"Erro ao importar: {e}")
    sys.exit(1)

TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

print("\n" + "="*60)
print("AUDITORIA RÁPIDA: 10 PRIMEIROS DIAS DE SETEMBRO 2026")
print("="*60 + "\n")

# Busca dados uma única vez
print("📥 Carregando dados...", end="", flush=True)
try:
    advbox_txs = advbox_get_all_transactions()
    print(" OK\n")
except Exception as e:
    print(f" ERRO: {e}")
    sys.exit(1)

tudo_bate = True
divergencias = []

for dia in range(1, 11):
    data = datetime(2026, 9, dia, tzinfo=tz).date()
    data_str = f"2026-09-{dia:02d}"

    try:
        # Asaas
        asaas_items = asaas_get_financial_transactions_do_dia(data)
        rec_asaas = sum(
            float(i.get("value", 0) or 0) for i in asaas_items
            if i.get("type") in TIPOS_RECEITA and float(i.get("value", 0) or 0) > 0
        )
        desp_asaas = sum(
            abs(float(i.get("value", 0) or 0)) for i in asaas_items
            if i.get("type") not in TIPOS_RECEITA and float(i.get("value", 0) or 0) < 0
        )

        # Advbox
        data_inicio = datetime.combine(data, datetime.min.time(), tzinfo=tz).timestamp()
        data_fim = datetime.combine(data, datetime.max.time(), tzinfo=tz).timestamp()
        txs_dia = [
            tx for tx in advbox_txs
            if data_inicio <= (tx.get("create_timestamp", 0) or 0) <= data_fim
        ]
        rec_advbox = sum(
            float(tx.get("value", 0) or 0) for tx in txs_dia
            if tx.get("type") == "CREDIT" and float(tx.get("value", 0) or 0) > 0
        )
        desp_advbox = sum(
            abs(float(tx.get("value", 0) or 0)) for tx in txs_dia
            if tx.get("type") == "DEBIT" and float(tx.get("value", 0) or 0) > 0
        )

        # Compara
        rec_ok = abs(rec_asaas - rec_advbox) < 0.01
        desp_ok = abs(desp_asaas - desp_advbox) < 0.01
        dia_ok = rec_ok and desp_ok

        status = "✓" if dia_ok else "✗"
        print(f"{status} {data_str}: REC {rec_asaas:>8.2f}={rec_advbox:>8.2f} | "
              f"DESP {desp_asaas:>8.2f}={'=' if desp_ok else '!'}{desp_advbox:>8.2f}")

        if not dia_ok:
            tudo_bate = False
            if not rec_ok:
                divergencias.append(f"  {data_str}: Receita Δ R$ {abs(rec_asaas - rec_advbox):.2f}")
            if not desp_ok:
                divergencias.append(f"  {data_str}: Despesa Δ R$ {abs(desp_asaas - desp_advbox):.2f}")

    except Exception as e:
        print(f"✗ {data_str}: ERRO - {e}")
        tudo_bate = False

print("\n" + "="*60)
if tudo_bate:
    print("✓ RESULTADO: Todos os 10 dias BATEM entre Asaas e Advbox")
else:
    print("✗ RESULTADO: Há divergências")
    if divergencias:
        print("\nDivergências encontradas:")
        for div in divergencias:
            print(div)

print("="*60 + "\n")
