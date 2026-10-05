#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug completo: estrutura e tipos de transações Asaas."""

import os
import sys
import json
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

print(f"\n🔍 DEBUG COMPLETO: Estrutura de Transações Asaas")
print(f"TIPOS_RECEITA esperados: {TIPOS_RECEITA}\n")
print("="*80)

# Verificar dia 1
data = datetime(2026, 9, 1, tzinfo=tz).date()
data_str = data.isoformat()
print(f"\n📥 Buscando transações para {data_str}...\n")

try:
    asaas_items = asaas_get_financial_transactions_do_dia(data_str)
    print(f"✓ Total retornado: {len(asaas_items)} transações\n")

    if asaas_items:
        # Contabilizar os tipos
        tipos_encontrados = Counter(i.get("type") for i in asaas_items)

        print("📊 TIPOS encontrados (contagem):")
        for tipo, count in tipos_encontrados.most_common():
            marker = "✓" if tipo in TIPOS_RECEITA else "✗"
            print(f"  {marker} {tipo}: {count}x")

        print("\n" + "="*80)
        print("🔍 ESTRUTURA: Primeiras 3 transações completas (JSON):\n")

        for idx, item in enumerate(asaas_items[:3], 1):
            print(f"Transação #{idx}:")
            print(json.dumps(item, indent=2, default=str))
            print()

        print("="*80)
        print("\n📊 ANÁLISE de VALORES por tipo:\n")

        for tipo in tipos_encontrados.keys():
            items_tipo = [i for i in asaas_items if i.get("type") == tipo]
            total = sum(float(i.get("value", 0) or 0) for i in items_tipo)
            media = total / len(items_tipo) if items_tipo else 0

            eh_receita = "✓ RECEITA" if tipo in TIPOS_RECEITA else "✗ despesa/taxa"
            print(f"{eh_receita} | {tipo}")
            print(f"     Quantidade: {len(items_tipo)}")
            print(f"     Total: R$ {total:,.2f}")
            print(f"     Média: R$ {media:,.2f}")
            print()

        print("="*80)

        # Calcular totais
        receitas_encontradas = sum(
            float(i.get("value", 0) or 0) for i in asaas_items
            if i.get("type") in TIPOS_RECEITA
        )
        despesas_encontradas = sum(
            float(i.get("value", 0) or 0) for i in asaas_items
            if i.get("type") not in TIPOS_RECEITA
        )

        print(f"\n💰 TOTAIS:")
        print(f"   Receitas (TIPOS_RECEITA): R$ {receitas_encontradas:,.2f}")
        print(f"   Despesas/Taxas: R$ {despesas_encontradas:,.2f}")
        print(f"   Saldo: R$ {receitas_encontradas - despesas_encontradas:,.2f}")
        print("\n" + "="*80 + "\n")
    else:
        print("❌ Nenhuma transação retornada!")

except Exception as e:
    print(f"❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
