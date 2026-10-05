#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug: examinar estrutura bruta de transações Advbox sem filtro de data."""

import os
import sys
import json
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

print(f"\n🔍 DEBUG RAW: Estrutura bruta de transações Advbox")
print("="*80)

# Buscar todas as transações
print(f"\n📥 Buscando todas as transações do Advbox...\n")
advbox_txs = advbox_get_all_transactions()
print(f"Total retornado: {len(advbox_txs)} transações\n")

if advbox_txs:
    print("="*80)
    print("🔍 PRIMEIRA TRANSAÇÃO (estrutura completa em JSON):\n")
    print(json.dumps(advbox_txs[0], indent=2, default=str))

    print("\n" + "="*80)
    print("\n🔍 CAMPOS disponíveis (primeiras 5 transações):\n")

    all_keys = set()
    for tx in advbox_txs[:5]:
        all_keys.update(tx.keys())
        print(f"Transação: {list(tx.keys())}")

    print(f"\n✓ Todos os campos encontrados: {sorted(all_keys)}")

    print("\n" + "="*80)
    print("\n📅 TIMESTAMPS encontrados (primeiras 10 transações):\n")

    for idx, tx in enumerate(advbox_txs[:10], 1):
        create_ts = tx.get("create_timestamp")
        update_ts = tx.get("update_timestamp")
        date_field = tx.get("date")

        print(f"{idx}. create_timestamp={create_ts} (type={type(create_ts).__name__})")
        if update_ts:
            print(f"   update_timestamp={update_ts} (type={type(update_ts).__name__})")
        if date_field:
            print(f"   date={date_field} (type={type(date_field).__name__})")

        # Try to convert to readable date
        if create_ts:
            try:
                if isinstance(create_ts, (int, float)):
                    dt = datetime.fromtimestamp(create_ts, tz=tz)
                    print(f"   → Data legível: {dt}")
            except:
                pass

    print("\n" + "="*80)
    print("\n📊 ANÁLISE de distribuição de timestamps:\n")

    timestamps = []
    for tx in advbox_txs:
        ts = tx.get("create_timestamp")
        if ts:
            timestamps.append(ts)

    if timestamps:
        timestamps.sort()
        print(f"Total com create_timestamp: {len(timestamps)}")
        print(f"Menor: {timestamps[0]}")
        print(f"Maior: {timestamps[-1]}")

        try:
            dt_min = datetime.fromtimestamp(timestamps[0], tz=tz)
            dt_max = datetime.fromtimestamp(timestamps[-1], tz=tz)
            print(f"Período: {dt_min} a {dt_max}")
        except Exception as e:
            print(f"Erro ao converter: {e}")

        print("\n" + "="*80)
        print("\n📆 Transações por mês/ano (amostra):\n")

        date_counter = Counter()
        for ts in timestamps[:100]:
            try:
                dt = datetime.fromtimestamp(ts, tz=tz)
                date_counter[dt.strftime("%Y-%m")] += 1
            except:
                date_counter["ERRO"] += 1

        for date_str, count in sorted(date_counter.items()):
            print(f"  {date_str}: {count}x")
else:
    print("❌ Nenhuma transação retornada!")

print("\n" + "="*80 + "\n")
