#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico detalhado: compara transações específicas de Asaas vs Advbox
para um dia específico, mostrando quais estão faltando ou divergem.
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

# Permitir override via variável de ambiente
DIA_ALVO = os.environ.get("DIA_ALVO", "2026-09-04")  # Dia com maior divergência

print(f"\n🔍 DIAGNÓSTICO: Comparação detalhada de transações para {DIA_ALVO}")
print("="*100)

# Buscar dados
print(f"\n📥 Buscando dados...")
advbox_txs = advbox_get_all_transactions()
print(f"   Advbox: {len(advbox_txs)} transações do banco ASAAS")

asaas_items = asaas_get_financial_transactions_do_dia(DIA_ALVO)
print(f"   Asaas: {len(asaas_items)} transações para {DIA_ALVO}\n")

# Filtrar para o dia
data = datetime.fromisoformat(DIA_ALVO).date()
data_str = data.isoformat()

txs_advbox_dia = [
    tx for tx in advbox_txs
    if tx.get("date_payment") == data_str
]

print(f"📊 RESUMO do dia {data_str}:")
print(f"   Asaas: {len(asaas_items)} eventos financeiros")
print(f"   Advbox: {len(txs_advbox_dia)} transações\n")

# ===== ANÁLISE ASAAS =====
print("="*100)
print("💰 ASAAS (Receitas)")
print("="*100 + "\n")

receitas_asaas = [
    i for i in asaas_items
    if i.get("type") in TIPOS_RECEITA and float(i.get("value", 0) or 0) > 0
]
print(f"Receitas encontradas: {len(receitas_asaas)}\n")

for idx, item in enumerate(receitas_asaas, 1):
    print(f"{idx}. R$ {float(item.get('value', 0)):>10.2f} | {item.get('type')}")
    print(f"   Descrição: {item.get('description', 'N/A')[:80]}")
    print(f"   ID: {item.get('id')}\n")

rec_asaas_total = sum(float(i.get("value", 0) or 0) for i in receitas_asaas)
print(f"TOTAL ASAAS RECEITAS: R$ {rec_asaas_total:,.2f}\n")

print("="*100)
print("💰 ASAAS (Despesas/Taxas)")
print("="*100 + "\n")

despesas_asaas = [
    i for i in asaas_items
    if i.get("type") not in TIPOS_RECEITA and float(i.get("value", 0) or 0) < 0
]
print(f"Despesas encontradas: {len(despesas_asaas)}\n")

for idx, item in enumerate(despesas_asaas, 1):
    print(f"{idx}. R$ {abs(float(item.get('value', 0)))>10.2f} | {item.get('type')}")
    print(f"   Descrição: {item.get('description', 'N/A')[:80]}")
    print(f"   ID: {item.get('id')}\n")

desp_asaas_total = sum(abs(float(i.get("value", 0) or 0)) for i in despesas_asaas)
print(f"TOTAL ASAAS DESPESAS: R$ {desp_asaas_total:,.2f}\n")

# ===== ANÁLISE ADVBOX =====
print("="*100)
print("💰 ADVBOX (Receitas/Income)")
print("="*100 + "\n")

receitas_advbox = [
    tx for tx in txs_advbox_dia
    if tx.get("entry_type") == "income" and float(tx.get("amount", 0) or 0) > 0
]
print(f"Receitas encontradas: {len(receitas_advbox)}\n")

for idx, tx in enumerate(receitas_advbox, 1):
    print(f"{idx}. R$ {float(tx.get('amount', 0)):>10.2f} | {tx.get('entry_type')}")
    print(f"   Descrição: {tx.get('description', 'N/A')[:80]}")
    print(f"   Categoria: {tx.get('category', 'N/A')}")
    print(f"   ID: {tx.get('id')}\n")

rec_advbox_total = sum(float(tx.get("amount", 0) or 0) for tx in receitas_advbox)
print(f"TOTAL ADVBOX RECEITAS: R$ {rec_advbox_total:,.2f}\n")

print("="*100)
print("💰 ADVBOX (Despesas/Expense)")
print("="*100 + "\n")

despesas_advbox = [
    tx for tx in txs_advbox_dia
    if tx.get("entry_type") == "expense" and float(tx.get("amount", 0) or 0) > 0
]
print(f"Despesas encontradas: {len(despesas_advbox)}\n")

for idx, tx in enumerate(despesas_advbox, 1):
    print(f"{idx}. R$ {float(tx.get('amount', 0)):>10.2f} | {tx.get('entry_type')}")
    print(f"   Descrição: {tx.get('description', 'N/A')[:80]}")
    print(f"   Categoria: {tx.get('category', 'N/A')}")
    print(f"   ID: {tx.get('id')}\n")

desp_advbox_total = sum(float(tx.get("amount", 0) or 0) for tx in despesas_advbox)
print(f"TOTAL ADVBOX DESPESAS: R$ {desp_advbox_total:,.2f}\n")

# ===== COMPARAÇÃO =====
print("="*100)
print("📊 COMPARAÇÃO")
print("="*100 + "\n")

print(f"RECEITAS:")
print(f"  Asaas:   R$ {rec_asaas_total:>10.2f}")
print(f"  Advbox:  R$ {rec_advbox_total:>10.2f}")
diff_rec = abs(rec_asaas_total - rec_advbox_total)
print(f"  Δ:       R$ {diff_rec:>10.2f} {'✓ Match' if diff_rec < 0.01 else '✗ Divergência'}\n")

print(f"DESPESAS:")
print(f"  Asaas:   R$ {desp_asaas_total:>10.2f}")
print(f"  Advbox:  R$ {desp_advbox_total:>10.2f}")
diff_desp = abs(desp_asaas_total - desp_advbox_total)
print(f"  Δ:       R$ {diff_desp:>10.2f} {'✓ Match' if diff_desp < 0.01 else '✗ Divergência'}\n")

print("="*100 + "\n")
