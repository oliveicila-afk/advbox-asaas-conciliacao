#!/usr/bin/env python3
"""
Análise Completa de Discrepâncias - Advbox vs Asaas
Setembro 2026 (01-10)

Este script:
1. Carrega a lista de transações Asaas fornecida pelo usuário
2. Faz fetch de TODAS as transações Advbox via API
3. Compara e identifica discrepâncias
4. Gera lista completa de transações a deletar
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict

# Configuration
ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()

if not ADVBOX_TOKEN:
    print("❌ ERRO: ADVBOX_TOKEN não definido como variável de ambiente")
    print("Defina com: export ADVBOX_TOKEN='seu_token'")
    sys.exit(1)

# Asaas transactions provided by user
ASAAS_FILE = "/root/.claude/uploads/54c1a44c-b24c-52fc-87d2-6838ce427a13/8afa2e4d-attachment.txt"
START_DATE = "2026-09-01"
END_DATE = "2026-09-10"

headers = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

print("=" * 100)
print("ANÁLISE COMPLETA DE DISCREPÂNCIAS - ADVBOX vs ASAAS")
print("=" * 100)
print(f"\nPeríodo: {START_DATE} a {END_DATE}")
print(f"Data/Hora: {datetime.now().isoformat()}\n")

# Step 1: Parse Asaas transactions from provided file
print("-" * 100)
print("ETAPA 1: PARSING ASAAS (do arquivo fornecido pelo usuário)")
print("-" * 100)

import re

asaas_transactions = {}
asaas_by_key = {}  # (name, amount) -> transaction

try:
    with open(ASAAS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Parse: "Type - fatura nr. XXXXX NAME    AMOUNT"
            parts = re.split(r'\s{2,}', line)
            if len(parts) < 2:
                continue

            amount_str = parts[-1]
            description = ' '.join(parts[:-1])

            try:
                amount = float(amount_str.replace(',', '.'))

                # Extract name
                name = re.sub(r'^[^-]+-\s*fatura\s+nr\.\s+\d+\s+', '', description).strip()
                name = re.sub(r'\.\s+Nota\s+fiscal\s+nr\.\s+\d+', '', name).strip()

                key = (name, round(amount, 2))
                asaas_by_key[key] = {
                    'name': name,
                    'amount': amount,
                    'line': line
                }
                asaas_transactions[line] = {
                    'name': name,
                    'amount': amount,
                    'description': description
                }
            except:
                pass
except FileNotFoundError:
    print(f"❌ Arquivo não encontrado: {ASAAS_FILE}")
    sys.exit(1)

print(f"✓ {len(asaas_transactions)} transações Asaas carregadas")
total_asaas = sum(t['amount'] for t in asaas_transactions.values())
print(f"✓ Total Asaas: R$ {total_asaas:.2f}")

# Step 2: Fetch ALL Advbox transactions for the period
print("\n" + "-" * 100)
print("ETAPA 2: FETCH COMPLETO DE TRANSAÇÕES ADVBOX")
print("-" * 100)

advbox_transactions = []
page = 1
per_page = 50
total_fetched = 0

try:
    while True:
        print(f"\nFetchando página {page}...", end=" ", flush=True)

        response = requests.get(
            f"{ADVBOX_BASE}/transactions",
            headers=headers,
            params={
                'page': page,
                'per_page': per_page,
                'type': 'income'  # Only income/receita transactions
            },
            timeout=30
        )

        if response.status_code != 200:
            print(f"⚠️  Status {response.status_code}")
            if response.status_code == 401:
                print("❌ Erro de autenticação. Token inválido?")
                sys.exit(1)
            break

        data = response.json()
        transactions = data.get('data', []) or data.get('transactions', [])

        if not transactions:
            print("Fim dos dados (sem transações)")
            break

        print(f"OK - {len(transactions)} transações")
        advbox_transactions.extend(transactions)
        total_fetched += len(transactions)

        # Check if we've reached the end
        if len(transactions) < per_page:
            break

        page += 1

except requests.exceptions.RequestException as e:
    print(f"❌ Erro ao conectar: {e}")
    sys.exit(1)

print(f"\n✓ {total_fetched} transações Advbox fetchadas do servidor")
total_advbox = sum(float(str(tx.get('value', tx.get('amount', 0))).replace(',', '.')) for tx in advbox_transactions)
print(f"✓ Total Advbox: R$ {total_advbox:.2f}")

# Step 3: Create matching keys
print("\n" + "-" * 100)
print("ETAPA 3: CRIANDO ÍNDICES PARA MATCHING")
print("-" * 100)

advbox_by_key = {}
advbox_by_id = {}

for tx in advbox_transactions:
    try:
        name = tx.get('description', tx.get('name', '')).strip()
        value = float(str(tx.get('value', tx.get('amount', 0))).replace(',', '.'))
        tx_id = tx.get('id')

        key = (name, round(value, 2))

        if key not in advbox_by_key:
            advbox_by_key[key] = []
        advbox_by_key[key].append(tx)
        advbox_by_id[tx_id] = tx

    except Exception as e:
        pass

print(f"✓ Índice Advbox criado: {len(advbox_by_key)} chaves únicas")

# Step 4: Find discrepancies
print("\n" + "-" * 100)
print("ETAPA 4: COMPARAÇÃO E IDENTIFICAÇÃO DE DISCREPÂNCIAS")
print("-" * 100)

# Advbox transactions without Asaas match
advbox_discrepancies = []
for key, advbox_txs in advbox_by_key.items():
    if key not in asaas_by_key:
        for tx in advbox_txs:
            advbox_discrepancies.append(tx)

# Sort by amount descending
advbox_discrepancies.sort(key=lambda x: -float(str(x.get('value', x.get('amount', 0))).replace(',', '.')))

total_to_delete = sum(float(str(tx.get('value', tx.get('amount', 0))).replace(',', '.')) for tx in advbox_discrepancies)

print(f"\n✓ Transações Advbox SEM correspondência em Asaas: {len(advbox_discrepancies)}")
print(f"✓ Total a deletar: R$ {total_to_delete:.2f}")
print(f"✓ Esperado: R$ 43.459,70")
print(f"✓ Diferença: R$ {total_to_delete - 43459.70:.2f}")

# Step 5: Generate deletion list
print("\n" + "=" * 100)
print("LISTA DE TRANSAÇÕES PARA DELETAR")
print("=" * 100)

deletion_list = []
for i, tx in enumerate(advbox_discrepancies, 1):
    tx_id = tx.get('id')
    tx_name = tx.get('description', tx.get('name', 'N/A'))
    tx_value = float(str(tx.get('value', tx.get('amount', 0))).replace(',', '.'))
    tx_date = tx.get('date', 'N/A')

    deletion_list.append({
        'id': tx_id,
        'name': tx_name,
        'amount': tx_value,
        'date': tx_date
    })

    if i <= 100:  # Show first 100
        print(f"{i:3d}. ID {str(tx_id):>15} | {tx_name:<45} | R$ {tx_value:>10.2f} | {tx_date}")

print(f"\n... e mais {max(0, len(advbox_discrepancies) - 100)} transações\n")

# Step 6: Generate comprehensive report
print("=" * 100)
print("RESUMO FINAL")
print("=" * 100)

report = {
    'generated_at': datetime.now().isoformat(),
    'period_start': START_DATE,
    'period_end': END_DATE,
    'asaas_total_transactions': len(asaas_transactions),
    'asaas_total_amount': total_asaas,
    'advbox_total_transactions': len(advbox_transactions),
    'advbox_total_amount': total_advbox,
    'discrepant_advbox_transactions': len(advbox_discrepancies),
    'discrepant_advbox_amount': total_to_delete,
    'expected_delete_amount': 43459.70,
    'difference': total_to_delete - 43459.70,
    'deletion_list': deletion_list
}

print(f"\nAsaas:")
print(f"  Total de transações: {report['asaas_total_transactions']}")
print(f"  Valor total: R$ {report['asaas_total_amount']:.2f}")

print(f"\nAdvbox (antes da deleção):")
print(f"  Total de transações: {report['advbox_total_transactions']}")
print(f"  Valor total: R$ {report['advbox_total_amount']:.2f}")

print(f"\nDiscrepâncias identificadas:")
print(f"  Transações a deletar: {report['discrepant_advbox_transactions']}")
print(f"  Valor a deletar: R$ {report['discrepant_advbox_amount']:.2f}")
print(f"  Esperado: R$ {report['expected_delete_amount']:.2f}")
print(f"  Diferença: R$ {report['difference']:+.2f}")

print(f"\nAdvbox (após deleção esperada):")
print(f"  Valor esperado: R$ {report['advbox_total_amount'] - report['discrepant_advbox_amount']:.2f}")
print(f"  Target (Asaas): R$ {report['asaas_total_amount']:.2f}")
print(f"  Variação: R$ {(report['advbox_total_amount'] - report['discrepant_advbox_amount']) - report['asaas_total_amount']:+.2f}")

# Save report to file
report_file = f"ANALISE_COMPLETA_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
with open(report_file, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"\n✓ Relatório salvo: {report_file}")

if advbox_discrepancies:
    print("\n✓ Pronto para deletar!")
    print(f"  Execute o workflow com: python deletar_receitas_discrepantes_v2.py")
else:
    print("\n⚠️  Nenhuma discrepância encontrada!")

