#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug: verificar transações do Advbox para dia 01 de setembro."""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from conciliar_v2 import advbox_get_all_transactions
except ImportError as e:
    print(f"Erro ao importar: {e}")
    sys.exit(1)

TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

print(f"\n🔍 DEBUG: Transações do Advbox")
print("="*80)

# Buscar todas as transações
print(f"\n📥 Buscando transações do Advbox...\n")
advbox_txs = advbox_get_all_transactions()
print(f"Total retornado: {len(advbox_txs)} transações\n")

# Filtrar para dia 1
data = datetime(2026, 9, 1, tzinfo=tz).date()
data_str = data.isoformat()

print(f"Filtrando para {data_str}:")

txs_dia = [
    tx for tx in advbox_txs
    if tx.get("date_payment") == data_str
]

print(f"Transações encontradas nesse período: {len(txs_dia)}\n")

if txs_dia:
    # Tipos de transações (entry_type em Advbox)
    tipos = Counter(tx.get("entry_type") for tx in txs_dia)
    print("📊 Tipos de transações encontradas:")
    for tipo, count in tipos.most_common():
        print(f"  {tipo}: {count}x")

    print("\n" + "="*80)
    print("DETALHES das primeiras 5 transações:")
    for idx, tx in enumerate(txs_dia[:5], 1):
        print(f"\n{idx}. ID={tx.get('id')} | entry_type={tx.get('entry_type')} | amount={tx.get('amount')}")
        print(f"   date_payment={tx.get('date_payment')} | name={tx.get('name', 'N/A')[:50]}")

    print("\n" + "="*80)
    print("\n💰 TOTAIS por tipo:")

    for tipo in tipos.keys():
        items = [tx for tx in txs_dia if tx.get("entry_type") == tipo]
        total = sum(float(tx.get("amount", 0) or 0) for tx in items)
        print(f"  {tipo}: R$ {total:,.2f}")

    print("\n" + "="*80)

    # Filtrar receitas (income) e despesas (expense)
    receitas = [
        tx for tx in txs_dia
        if tx.get("entry_type") == "income" and float(tx.get("amount", 0) or 0) > 0
    ]
    despesas = [
        tx for tx in txs_dia
        if tx.get("entry_type") == "expense" and float(tx.get("amount", 0) or 0) > 0
    ]

    rec_total = sum(float(tx.get("amount", 0) or 0) for tx in receitas)
    desp_total = sum(float(tx.get("amount", 0) or 0) for tx in despesas)

    print(f"\n✓ Receitas (income, amount > 0): {len(receitas)} | Total: R$ {rec_total:,.2f}")
    print(f"✗ Despesas (expense, amount > 0): {len(despesas)} | Total: R$ {desp_total:,.2f}")

else:
    print("❌ Nenhuma transação encontrada nesse período!")

print("\n" + "="*80 + "\n")
