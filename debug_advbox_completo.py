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
data_inicio = datetime.combine(data, datetime.min.time(), tzinfo=tz).timestamp()
data_fim = datetime.combine(data, datetime.max.time(), tzinfo=tz).timestamp()

print(f"Filtrando para {data}:")
print(f"  Início (timestamp): {data_inicio}")
print(f"  Fim (timestamp): {data_fim}\n")

txs_dia = [
    tx for tx in advbox_txs
    if data_inicio <= (tx.get("create_timestamp", 0) or 0) <= data_fim
]

print(f"Transações encontradas nesse período: {len(txs_dia)}\n")

if txs_dia:
    # Tipos de transações
    tipos = Counter(tx.get("type") for tx in txs_dia)
    print("📊 Tipos de transações encontradas:")
    for tipo, count in tipos.most_common():
        print(f"  {tipo}: {count}x")

    print("\n" + "="*80)
    print("DETALHES das primeiras 5 transações:")
    for idx, tx in enumerate(txs_dia[:5], 1):
        print(f"\n{idx}. ID={tx.get('id')} | type={tx.get('type')} | value={tx.get('value')}")
        print(f"   timestamp={tx.get('create_timestamp')} | name={tx.get('name', 'N/A')[:50]}")

    print("\n" + "="*80)
    print("\n💰 TOTAIS por tipo:")

    for tipo in tipos.keys():
        items = [tx for tx in txs_dia if tx.get("type") == tipo]
        total = sum(float(tx.get("value", 0) or 0) for tx in items)
        print(f"  {tipo}: R$ {total:,.2f}")

    print("\n" + "="*80)

    # Filtrar receitas (CREDIT)
    receitas = [
        tx for tx in txs_dia
        if tx.get("type") == "CREDIT" and float(tx.get("value", 0) or 0) > 0
    ]
    despesas = [
        tx for tx in txs_dia
        if tx.get("type") == "DEBIT" and float(tx.get("value", 0) or 0) > 0
    ]

    rec_total = sum(float(tx.get("value", 0) or 0) for tx in receitas)
    desp_total = sum(float(tx.get("value", 0) or 0) for tx in despesas)

    print(f"\n✓ Receitas (CREDIT, value > 0): {len(receitas)} | Total: R$ {rec_total:,.2f}")
    print(f"✗ Despesas (DEBIT, value > 0): {len(despesas)} | Total: R$ {desp_total:,.2f}")

else:
    print("❌ Nenhuma transação encontrada nesse período!")

print("\n" + "="*80 + "\n")
