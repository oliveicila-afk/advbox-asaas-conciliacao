#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug: quais são os tipos de transações retornadas pela Asaas."""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from conciliar_v2 import (
        asaas_get_financial_transactions_do_dia,
        TIPOS_RECEITA,
    )
except ImportError as e:
    print(f"Erro ao importar: {e}")
    sys.exit(1)

TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

print(f"\n📊 TIPOS_RECEITA esperados: {TIPOS_RECEITA}\n")
print("="*70)

# Verificar dia 1
data = datetime(2026, 9, 1, tzinfo=tz).date()
print(f"\n📥 Buscando transações para {data}...\n")

asaas_items = asaas_get_financial_transactions_do_dia(data)
print(f"Total retornado: {len(asaas_items)} transações\n")

if asaas_items:
    # Contabilizar os tipos
    tipos_encontrados = Counter(i.get("type") for i in asaas_items)
    print("📊 Tipos de transações encontradas:")
    for tipo, count in tipos_encontrados.most_common():
        print(f"  - {tipo}: {count}x")

    print("\n" + "="*70)
    print("🔍 DETALHES das primeiras 5 transações:\n")
    for idx, item in enumerate(asaas_items[:5], 1):
        print(f"{idx}. type={item.get('type')} | value={item.get('value')} | description={item.get('description', 'N/A')[:50]}")

    print("\n" + "="*70)
    print(f"\n✓ Total que passariam no filtro TIPOS_RECEITA: "
          f"{sum(1 for i in asaas_items if i.get('type') in TIPOS_RECEITA)}")
    print(f"✓ Total NÃO em TIPOS_RECEITA: "
          f"{sum(1 for i in asaas_items if i.get('type') not in TIPOS_RECEITA)}")
else:
    print("❌ Nenhuma transação retornada!")

print("\n" + "="*70 + "\n")
