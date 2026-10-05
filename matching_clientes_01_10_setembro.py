#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matching de clientes entre Asaas e Advbox (01-10 de setembro)

Identifica:
1. Clientes que estão em Asaas mas NÃO estão em Advbox
2. Clientes que estão em Advbox mas NÃO estão em Asaas
3. Clientes que estão em ambos
"""

import os
import sys
from datetime import datetime, timedelta
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

print("\n" + "="*100)
print("🔍 MATCHING DE CLIENTES: Asaas vs Advbox (01-10 de Setembro)")
print("="*100 + "\n")

# ===== CARREGAR DADOS =====
print("📥 Carregando dados do Advbox...", end="", flush=True)
try:
    advbox_txs = advbox_get_all_transactions()
    print(" ✓\n")
except Exception as e:
    print(f" ❌ ERRO: {e}")
    sys.exit(1)

# ===== PERÍODO: 01-10 DE SETEMBRO =====
asaas_clientes = defaultdict(lambda: {"valores": [], "total": 0, "qtd": 0})
advbox_clientes = defaultdict(lambda: {"valores": [], "total": 0, "qtd": 0})

print("📥 Carregando dados do Asaas (01-10 de setembro)...\n")

for dia in range(1, 11):
    data = datetime(2026, 9, dia, tzinfo=tz).date()
    data_str = data.isoformat()

    try:
        items = asaas_get_financial_transactions_do_dia(data_str)

        for item in items:
            valor = float(item.get("value", 0) or 0)
            if valor > 0:  # Apenas receitas
                desc = item.get("description", "")
                client_name = desc.split("-")[0].strip() if "-" in desc else desc[:50]

                if client_name:
                    asaas_clientes[client_name]["valores"].append(valor)
                    asaas_clientes[client_name]["total"] += valor
                    asaas_clientes[client_name]["qtd"] += 1

    except Exception as e:
        print(f"⚠️  Erro ao buscar 09/{dia:02d}: {e}")

print(f"✓ Total de clientes únicos em Asaas: {len(asaas_clientes)}\n")

# ===== ADVBOX =====
print("📥 Carregando dados do Advbox (01-10 de setembro)...\n")

for tx in advbox_txs:
    data_payment = tx.get("date_payment")
    if data_payment and data_payment.startswith("2026-09") and int(data_payment[8:10]) <= 10:
        if tx.get("entry_type") == "income":
            valor = float(tx.get("amount", 0) or 0)
            if valor > 0:
                desc = tx.get("description", "")
                client_name = desc.split("-")[0].strip() if "-" in desc else desc[:50]

                if client_name:
                    advbox_clientes[client_name]["valores"].append(valor)
                    advbox_clientes[client_name]["total"] += valor
                    advbox_clientes[client_name]["qtd"] += 1

print(f"✓ Total de clientes únicos em Advbox: {len(advbox_clientes)}\n")

# ===== ANÁLISE =====
print("\n" + "="*100)
print("📊 ANÁLISE DE MATCHING")
print("="*100 + "\n")

# Clientes só em Asaas
asaas_only = set(asaas_clientes.keys()) - set(advbox_clientes.keys())
# Clientes só em Advbox
advbox_only = set(advbox_clientes.keys()) - set(asaas_clientes.keys())
# Clientes em ambos
both = set(asaas_clientes.keys()) & set(advbox_clientes.keys())

print(f"🔴 CLIENTES APENAS EM ASAAS (não estão em Advbox): {len(asaas_only)}")
print(f"   Total de receita: R$ {sum(asaas_clientes[c]['total'] for c in asaas_only):,.2f}\n")

if asaas_only:
    for client in sorted(asaas_only, key=lambda c: asaas_clientes[c]['total'], reverse=True):
        dados = asaas_clientes[client]
        print(f"  • {client[:60]:60} | R$ {dados['total']:>12.2f} ({dados['qtd']} transações)")

print(f"\n🟠 CLIENTES APENAS EM ADVBOX (não estão em Asaas): {len(advbox_only)}")
print(f"   Total de receita: R$ {sum(advbox_clientes[c]['total'] for c in advbox_only):,.2f}\n")

if advbox_only:
    for client in sorted(advbox_only, key=lambda c: advbox_clientes[c]['total'], reverse=True)[:20]:
        dados = advbox_clientes[client]
        print(f"  • {client[:60]:60} | R$ {dados['total']:>12.2f} ({dados['qtd']} transações)")
    if len(advbox_only) > 20:
        print(f"  ... e mais {len(advbox_only) - 20} clientes")

print(f"\n🟢 CLIENTES EM AMBOS OS SISTEMAS: {len(both)}")
print(f"   Total Asaas: R$ {sum(asaas_clientes[c]['total'] for c in both):,.2f}")
print(f"   Total Advbox: R$ {sum(advbox_clientes[c]['total'] for c in both):,.2f}\n")

# ===== TOTAIS =====
print("\n" + "="*100)
print("📈 RESUMO GERAL (01-10 de Setembro)")
print("="*100 + "\n")

total_asaas = sum(c['total'] for c in asaas_clientes.values())
total_advbox = sum(c['total'] for c in advbox_clientes.values())
total_asaas_only = sum(asaas_clientes[c]['total'] for c in asaas_only)
total_advbox_only = sum(advbox_clientes[c]['total'] for c in advbox_only)

print(f"Asaas Total:            R$ {total_asaas:>12.2f}")
print(f"Advbox Total:           R$ {total_advbox:>12.2f}")
print(f"Diferença:              R$ {abs(total_asaas - total_advbox):>12.2f}\n")

print(f"Apenas em Asaas:        R$ {total_asaas_only:>12.2f} ({len(asaas_only)} clientes)")
print(f"Apenas em Advbox:       R$ {total_advbox_only:>12.2f} ({len(advbox_only)} clientes)")
print(f"Em ambos os sistemas:   R$ {sum(asaas_clientes[c]['total'] for c in both):>12.2f} ({len(both)} clientes)\n")

print("="*100 + "\n")
