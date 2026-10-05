#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise de Matching Manual: compara transações Asaas vs Advbox
para um dia específico, tentando fazer matching por descrição e valor.
"""

import os
import sys
import json
from datetime import datetime
from difflib import SequenceMatcher

DIA_ALVO = os.environ.get("DIA_ALVO", "2026-09-08")
CACHE_FILE = os.environ.get("CACHE_FILE", "transactions_cache.json")

if not os.path.exists(CACHE_FILE):
    print(f"❌ Cache não encontrado: {CACHE_FILE}")
    sys.exit(1)

with open(CACHE_FILE, "r") as f:
    cache = json.load(f)

advbox_txs = cache.get("advbox", [])
asaas_data = cache.get("asaas", {})

asaas_items = asaas_data.get(DIA_ALVO, [])
txs_advbox_dia = [tx for tx in advbox_txs if tx.get("date_payment") == DIA_ALVO]

print(f"\n🔗 ANÁLISE DE MATCHING: {DIA_ALVO}")
print("="*100)

# Tipos de receita
TIPOS_RECEITA = [
    "CREDIT_CARD_SALE", "DEPOSIT", "CREDIT", "PIX_TRANSFER_RECEIVED",
    "PIX_RECEIVED", "TEDReceived", "DOCReceived",
]

# Separar por tipo
despesas_asaas = [
    i for i in asaas_items
    if i.get("type") not in TIPOS_RECEITA and float(i.get("value", 0) or 0) < 0
]
despesas_advbox = [
    tx for tx in txs_advbox_dia
    if tx.get("entry_type") == "expense" and float(tx.get("amount", 0) or 0) > 0
]

print(f"\n💰 DESPESAS - Tentando fazer matching")
print(f"   Asaas: {len(despesas_asaas)} itens")
print(f"   Advbox: {len(despesas_advbox)} itens\n")

def similarity(a, b):
    """Calcula similaridade entre dois strings (0-1)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_match(asaas_tx, advbox_list, threshold=0.6):
    """Tenta encontrar o melhor match para uma transação Asaas em Advbox"""
    asaas_desc = asaas_tx.get("description", "").lower()
    asaas_value = abs(float(asaas_tx.get("value", 0) or 0))

    best_match = None
    best_score = 0

    for advbox_tx in advbox_list:
        advbox_desc = advbox_tx.get("description", "").lower()
        advbox_value = float(advbox_tx.get("amount", 0) or 0)

        # Similaridade de descrição
        desc_sim = similarity(asaas_desc, advbox_desc)

        # Compatibilidade de valor (dentro de 1%)
        value_match = abs(asaas_value - advbox_value) < (asaas_value * 0.01) if asaas_value > 0 else True

        # Score combinado
        score = desc_sim if value_match else desc_sim * 0.5

        if score > best_score and score >= threshold:
            best_score = score
            best_match = (advbox_tx, score)

    return best_match

# Rastrear matches
matched = []
unmatched_asaas = []

print("MATCHES ENCONTRADOS:")
print("-" * 100)

for idx, asaas_tx in enumerate(despesas_asaas, 1):
    match = find_best_match(asaas_tx, despesas_advbox, threshold=0.5)

    if match:
        advbox_tx, score = match
        matched.append((asaas_tx, advbox_tx, score))

        asaas_val = abs(float(asaas_tx.get("value", 0) or 0))
        advbox_val = float(advbox_tx.get("amount", 0) or 0)

        status = "✓" if abs(asaas_val - advbox_val) < 0.01 else "~"
        print(f"{status} {idx}. [{score:.0%}] Asaas R$ {asaas_val:>10.2f} = Advbox R$ {advbox_val:>10.2f}")
        print(f"   Asaas:  {asaas_tx.get('description', '')[:70]}")
        print(f"   Advbox: {advbox_tx.get('description', '')[:70]}\n")
    else:
        unmatched_asaas.append(asaas_tx)

print("\n" + "="*100)
print(f"SEM MATCH EM ADVBOX ({len(unmatched_asaas)} itens):")
print("-" * 100)

for idx, asaas_tx in enumerate(unmatched_asaas, 1):
    asaas_val = abs(float(asaas_tx.get("value", 0) or 0))
    print(f"{idx}. R$ {asaas_val:>10.2f} | {asaas_tx.get('type')}")
    print(f"   {asaas_tx.get('description', '')[:80]}")
    print(f"   ID: {asaas_tx.get('id')}\n")

# Transações Advbox sem match em Asaas
matched_advbox_ids = {tx.get('id') for _, advbox_tx, _ in matched for tx in [advbox_tx]}
unmatched_advbox = [tx for tx in despesas_advbox if tx.get('id') not in matched_advbox_ids]

print("="*100)
print(f"TRANSAÇÕES ADVBOX SEM MATCH EM ASAAS ({len(unmatched_advbox)} itens):")
print("-" * 100)

for idx, advbox_tx in enumerate(unmatched_advbox, 1):
    advbox_val = float(advbox_tx.get("amount", 0) or 0)
    print(f"{idx}. R$ {advbox_val:>10.2f}")
    print(f"   {advbox_tx.get('description', '')[:80]}")
    print(f"   Categoria: {advbox_tx.get('category', 'N/A')}")
    print(f"   ID: {advbox_tx.get('id')}\n")

# Resumo
print("="*100)
print("📊 RESUMO DE MATCHING")
print("-" * 100)

asaas_total = sum(abs(float(tx.get("value", 0) or 0)) for tx in despesas_asaas)
advbox_total = sum(float(tx.get("amount", 0) or 0) for tx in despesas_advbox)
matched_total = sum(float(adv_tx.get("amount", 0) or 0) for _, adv_tx, _ in matched)

unmatched_asaas_total = sum(abs(float(tx.get("value", 0) or 0)) for tx in unmatched_asaas)
unmatched_advbox_total = sum(float(tx.get("amount", 0) or 0) for tx in unmatched_advbox)

print(f"Matches: {len(matched)}/{len(despesas_asaas)} despesas Asaas")
print(f"Matched value: R$ {matched_total:,.2f} / R$ {asaas_total:,.2f}")
print()
print(f"Sem match em Advbox: {len(unmatched_asaas)} itens = R$ {unmatched_asaas_total:,.2f}")
print(f"Sem match em Asaas: {len(unmatched_advbox)} itens = R$ {unmatched_advbox_total:,.2f}")
print()
print(f"Divergência não reconciliada: R$ {abs(unmatched_asaas_total - unmatched_advbox_total):,.2f}")

print("="*100 + "\n")
