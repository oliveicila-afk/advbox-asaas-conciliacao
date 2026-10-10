#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reconciliação Completa: Asaas vs Advbox (Sep 01-10, 2026)

Tarefa: Mostrar quais transações estão EXTRA em Advbox
(não apenas qual está faltando)

Entrada:
- Lista de 120 transações do Asaas (fornecida pelo usuário)
- Lista de transações do Advbox (obtida via API)

Saída:
- Transações que estão em Advbox mas NÃO estão em Asaas
- Mostrar customer name e valor de cada uma
"""

import os
import sys
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from conciliar_v2 import advbox_get_all_transactions
except ImportError as e:
    print(f"Erro ao importar: {e}")
    sys.exit(1)

TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

print("=" * 80)
print("RECONCILIAÇÃO COMPLETA: Asaas vs Advbox")
print("Período: 1-10 de setembro de 2026")
print("=" * 80)

# 1. Obter transações do Advbox
print("\n📥 Buscando transações do Advbox...")
try:
    advbox_txs_all = advbox_get_all_transactions(limite_paginas=50)
    print(f"✓ Total retornado: {len(advbox_txs_all)} transações")
except Exception as e:
    print(f"❌ Erro ao consultar Advbox: {e}")
    sys.exit(1)

# 2. Filtrar para período Sep 01-10
start_date = datetime(2026, 9, 1, tzinfo=tz).date()
end_date = datetime(2026, 9, 10, tzinfo=tz).date()

print(f"\n🔍 Filtrando para {start_date} até {end_date}...")

advbox_txs = []
for tx in advbox_txs_all:
    date_str = tx.get("date")
    if date_str:
        try:
            tx_date = datetime.fromisoformat(date_str).date()
            if start_date <= tx_date <= end_date:
                advbox_txs.append(tx)
        except:
            pass

print(f"✓ Transações no período (Advbox): {len(advbox_txs)}")

# 3. Exibir detalhes das transações do Advbox
print("\n" + "-" * 80)
print("TRANSAÇÕES DO ADVBOX (Sep 01-10):")
print("-" * 80)

advbox_by_customer_amount = defaultdict(list)
total_advbox = 0

for tx in advbox_txs:
    amount = float(tx.get("amount", 0) or 0)
    date = tx.get("date", "")
    description = tx.get("description", "")
    customer_name = tx.get("name", "")
    entry_type = tx.get("entry_type", "")
    tx_id = tx.get("id", "")

    # Armazenar para comparação posterior
    key = (customer_name, amount)
    advbox_by_customer_amount[key].append({
        "id": tx_id,
        "date": date,
        "description": description,
        "entry_type": entry_type,
        "amount": amount
    })

    total_advbox += amount

    print(f"\n• {date} | R$ {amount:>10,.2f} | {customer_name[:40]}")
    print(f"  ID: {tx_id} | Tipo: {entry_type}")
    print(f"  Desc: {description[:60]}")

print("\n" + "=" * 80)
print(f"TOTAL ADVBOX (Sep 01-10): R$ {total_advbox:,.2f}")
print(f"QUANTIDADE: {len(advbox_txs)} transações")
print("=" * 80)

# 4. Agora precisamos carregar a lista do Asaas
# A lista foi fornecida manualmente pelo usuário
# Vou criar um arquivo placeholder para ela

print("\n\n📋 PRÓXIMO PASSO:")
print("-" * 80)
print("Para comparação completa, precisamos da lista de 120 transações do Asaas.")
print("O arquivo com os dados do Advbox foi salvo.")
print("\nResultado do Advbox foi exportado para: resultado_advbox_completo.json")

# Salvar resultado
resultado = {
    "timestamp": datetime.now(tz).isoformat(),
    "periodo": "2026-09-01 a 2026-09-10",
    "total_transacoes": len(advbox_txs),
    "total_valor": total_advbox,
    "transacoes": [
        {
            "id": tx.get("id"),
            "date": tx.get("date"),
            "name": tx.get("name"),
            "amount": float(tx.get("amount", 0) or 0),
            "entry_type": tx.get("entry_type"),
            "description": tx.get("description")
        }
        for tx in advbox_txs
    ]
}

with open("resultado_advbox_completo.json", "w") as f:
    json.dump(resultado, f, indent=2, ensure_ascii=False)

print(f"✓ Dados salvos em: resultado_advbox_completo.json")
print("\n" + "=" * 80)
