#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditoria de RECEITAS: Verifica se receitas batem entre Asaas e Advbox
para os primeiros 10 dias de setembro.
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

print("\n" + "="*70)
print("💰 AUDITORIA DE RECEITAS: ASAAS vs ADVBOX")
print("Período: 1-10 de setembro 2026")
print("="*70 + "\n")

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

print(f"{'Dia':<6} | {'Asaas':>12} | {'Advbox':>12} | {'Δ':>12} | Status")
print("-" * 70)

for dia in range(1, 11):
    data = datetime(2026, 9, dia, tzinfo=tz).date()
    data_str = data.isoformat()

    try:
        # Asaas - RECEITAS
        asaas_items = asaas_get_financial_transactions_do_dia(data_str)
        rec_asaas = sum(
            float(i.get("value", 0) or 0) for i in asaas_items
            if i.get("type") in TIPOS_RECEITA and float(i.get("value", 0) or 0) > 0
        )

        # Advbox - RECEITAS
        data_str_advbox = data.isoformat()
        txs_dia = [
            tx for tx in advbox_txs
            if tx.get("date_payment") == data_str_advbox
        ]
        rec_advbox = sum(
            float(tx.get("amount", 0) or 0) for tx in txs_dia
            if tx.get("entry_type") == "income" and float(tx.get("amount", 0) or 0) > 0
        )

        # Compara
        rec_ok = abs(rec_asaas - rec_advbox) < 0.01
        diff = abs(rec_asaas - rec_advbox)

        status = "✓" if rec_ok else "✗"
        print(f"{dia:<6} | R${rec_asaas:>10.2f} | R${rec_advbox:>10.2f} | R${diff:>10.2f} | {status}")

        if not rec_ok:
            tudo_bate = False
            divergencias.append((data_str, rec_asaas, rec_advbox, diff))

    except Exception as e:
        print(f"{dia:<6} | ERRO: {e}")
        tudo_bate = False

print("\n" + "="*70)
if tudo_bate:
    print("✅ RESULTADO: Todas as receitas BATEM entre Asaas e Advbox")
else:
    print(f"⚠️  RESULTADO: {len(divergencias)} dia(s) com divergência de receita")
    if divergencias:
        print("\nDivergências encontradas:")
        for data, asaas, advbox, diff in divergencias:
            print(f"  {data}: Asaas R$ {asaas:.2f} vs Advbox R$ {advbox:.2f} (Δ R$ {diff:.2f})")
print("="*70 + "\n")
