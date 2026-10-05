#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise detalhada de transações por DATA e VALOR
Para identificar as transações que faltam lançar em Advbox
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from conciliar_v2 import (
        advbox_get_all_transactions,
        asaas_get_financial_transactions_do_dia,
    )
except ImportError as e:
    print(f"Erro ao importar: {e}")
    sys.exit(1)

TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

print("\n" + "="*120)
print("💰 ANÁLISE DETALHADA POR DATA E VALOR: Asaas vs Advbox (01-10 Setembro)")
print("="*120 + "\n")

# ===== CARREGAR DADOS =====
print("📥 Carregando dados do Advbox...", end="", flush=True)
try:
    advbox_txs = advbox_get_all_transactions()
    print(" ✓\n")
except Exception as e:
    print(f" ❌ ERRO: {e}")
    sys.exit(1)

# Agrupar Advbox por DATA
advbox_por_data = defaultdict(list)
print("📥 Agrupando dados do Advbox (01-10 setembro)...\n")
for tx in advbox_txs:
    data_payment = tx.get("date_payment")
    if data_payment and data_payment.startswith("2026-09"):
        dia = int(data_payment[8:10])
        if dia <= 10:
            if tx.get("entry_type") == "income":
                valor = float(tx.get("amount", 0) or 0)
                if valor > 0:
                    advbox_por_data[dia].append({
                        "data": data_payment,
                        "valor": valor,
                        "descricao": tx.get("description", ""),
                        "categoria": tx.get("category", ""),
                    })

# ===== ASAAS POR DATA =====
print("📥 Carregando dados do Asaas (01-10 de setembro)...\n")

asaas_por_data = defaultdict(list)
asaas_todos = {}  # Para armazenar todos os dados

for dia in range(1, 11):
    data = datetime(2026, 9, dia, tzinfo=tz).date()
    data_str = data.isoformat()

    try:
        items = asaas_get_financial_transactions_do_dia(data_str)

        for item in items:
            valor = float(item.get("value", 0) or 0)
            if valor > 0:  # Apenas receitas
                asaas_por_data[dia].append({
                    "data": data_str,
                    "valor": valor,
                    "descricao": item.get("description", ""),
                    "id": item.get("id", ""),
                    "tipo": item.get("type", ""),
                })

    except Exception as e:
        print(f"⚠️  Erro ao buscar {data_str}: {e}")

# ===== ANÁLISE POR DIA =====
print("\n" + "="*120)
print("📊 ANÁLISE POR DIA")
print("="*120 + "\n")

divergencias_por_dia = {}

for dia in range(1, 11):
    asaas_txs = asaas_por_data[dia]
    advbox_txs = advbox_por_data[dia]

    total_asaas = sum(tx["valor"] for tx in asaas_txs)
    total_advbox = sum(tx["valor"] for tx in advbox_txs)
    divergencia = total_asaas - total_advbox

    print(f"📅 **09/{dia:02d}**")
    print(f"   Asaas:   R$ {total_asaas:>10.2f} ({len(asaas_txs):>2} transações)")
    print(f"   Advbox:  R$ {total_advbox:>10.2f} ({len(advbox_txs):>2} transações)")

    if divergencia > 0.01:
        print(f"   ❌ Divergência: R$ {divergencia:.2f} (falta em Advbox)")
        divergencias_por_dia[dia] = divergencia

        # Mostrar detalhes
        print(f"\n   📋 Detalhes do Asaas:")
        for tx in sorted(asaas_txs, key=lambda x: x["valor"], reverse=True):
            print(f"      • R$ {tx['valor']:>10.2f} | {tx['descricao'][:70]}")

        print(f"\n   📋 Detalhes do Advbox:")
        for tx in sorted(advbox_txs, key=lambda x: x["valor"], reverse=True):
            print(f"      • R$ {tx['valor']:>10.2f} | {tx['descricao'][:70]}")
    elif abs(divergencia) < 0.01:
        print(f"   ✅ Balanceado")
    else:
        print(f"   🟡 Advbox tem mais: R$ {abs(divergencia):.2f}")

    print()

# ===== TOTAIS =====
print("\n" + "="*120)
print("📈 RESUMO GERAL")
print("="*120 + "\n")

total_asaas_geral = sum(sum(tx["valor"] for tx in asaas_por_data[d]) for d in range(1, 11))
total_advbox_geral = sum(sum(tx["valor"] for tx in advbox_por_data[d]) for d in range(1, 11))
divergencia_geral = total_asaas_geral - total_advbox_geral

print(f"Asaas Total:          R$ {total_asaas_geral:>12.2f}")
print(f"Advbox Total:         R$ {total_advbox_geral:>12.2f}")
print(f"Divergência Total:    R$ {divergencia_geral:>12.2f}\n")

if divergencias_por_dia:
    print("Dias com divergência (falta em Advbox):")
    for dia in sorted(divergencias_por_dia.keys()):
        print(f"  • 09/{dia:02d}: R$ {divergencias_por_dia[dia]:>10.2f}")

print("\n" + "="*120 + "\n")
