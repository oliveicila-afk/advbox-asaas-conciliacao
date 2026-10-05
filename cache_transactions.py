#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cache de transações: salva dados da API em JSON para análise offline.
Útil quando os tokens não estão disponíveis em uma sessão de continuação.
"""

import os
import sys
import json
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

print("\n📥 Carregando dados da API...")

# Carregar dados
try:
    advbox_txs = advbox_get_all_transactions()
    print(f"✓ Advbox: {len(advbox_txs)} transações")
except Exception as e:
    print(f"✗ Erro ao carregar Advbox: {e}")
    advbox_txs = []

# Carregar Asaas para os 10 primeiros dias de setembro
asaas_data = {}
for dia in range(1, 11):
    data = datetime(2026, 9, dia, tzinfo=tz).date()
    data_str = data.isoformat()
    try:
        items = asaas_get_financial_transactions_do_dia(data_str)
        asaas_data[data_str] = items
        print(f"✓ Asaas {data_str}: {len(items)} eventos")
    except Exception as e:
        print(f"✗ Erro ao carregar Asaas {data_str}: {e}")
        asaas_data[data_str] = []

# Salvar cache
cache = {
    "timestamp": datetime.now(tz).isoformat(),
    "timezone": TIMEZONE,
    "advbox": advbox_txs,
    "asaas": asaas_data,
}

cache_file = "transactions_cache.json"
with open(cache_file, "w") as f:
    json.dump(cache, f, indent=2, default=str)

print(f"\n✓ Cache salvo em {cache_file}")
print(f"  Tamanho: {os.path.getsize(cache_file)} bytes")
