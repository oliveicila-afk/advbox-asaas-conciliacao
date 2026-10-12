#!/usr/bin/env python3
"""
Debug script to test different Advbox account filter parameter names
and values to find the correct way to filter by ASAAS account.
"""

import os
import requests
import sys

ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
TARGET_DATE = os.environ.get("TARGET_DATE", "2026-09-01").strip()

# Open output file for writing
output_file = open("debug_account_filter_output.txt", "w", encoding="utf-8")

def log(msg=""):
    """Print to both stdout and file"""
    print(msg)
    output_file.write(msg + "\n")
    output_file.flush()

log("=" * 100)
log("TESTE DE FILTROS DE CONTA DO ADVBOX")
log("=" * 100)

if not ADVBOX_TOKEN:
    log("❌ ADVBOX_TOKEN não definido")
    output_file.close()
    exit(1)

headers = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "Accept": "application/json"
}

# Test different parameter combinations
test_cases = [
    {
        "name": "Sem filtro de conta (baseline)",
        "params": {
            "type": "income",
            "payment_date_from": TARGET_DATE,
            "payment_date_to": TARGET_DATE,
            "status": "paid",
            "per_page": 100,
            "page": 1,
        }
    },
    {
        "name": "Com account_type=asaas",
        "params": {
            "type": "income",
            "payment_date_from": TARGET_DATE,
            "payment_date_to": TARGET_DATE,
            "status": "paid",
            "account_type": "asaas",
            "per_page": 100,
            "page": 1,
        }
    },
    {
        "name": "Com account=asaas",
        "params": {
            "type": "income",
            "payment_date_from": TARGET_DATE,
            "payment_date_to": TARGET_DATE,
            "status": "paid",
            "account": "asaas",
            "per_page": 100,
            "page": 1,
        }
    },
    {
        "name": "Com bank_type=asaas",
        "params": {
            "type": "income",
            "payment_date_from": TARGET_DATE,
            "payment_date_to": TARGET_DATE,
            "status": "paid",
            "bank_type": "asaas",
            "per_page": 100,
            "page": 1,
        }
    },
    {
        "name": "Com account_id=1",
        "params": {
            "type": "income",
            "payment_date_from": TARGET_DATE,
            "payment_date_to": TARGET_DATE,
            "status": "paid",
            "account_id": "1",
            "per_page": 100,
            "page": 1,
        }
    },
    {
        "name": "Com account_type=ASAAS (maiúsculo)",
        "params": {
            "type": "income",
            "payment_date_from": TARGET_DATE,
            "payment_date_to": TARGET_DATE,
            "status": "paid",
            "account_type": "ASAAS",
            "per_page": 100,
            "page": 1,
        }
    },
]

for test in test_cases:
    log(f"\n\n{'=' * 100}")
    log(f"TESTE: {test['name']}")
    log(f"{'=' * 100}")

    try:
        resp = requests.get(
            "https://app.advbox.com.br/api/v1/transactions",
            headers=headers,
            params=test['params'],
            timeout=10
        )

        log(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()

            # Extract transaction data
            transactions = data.get("data", []) or data.get("transactions", [])
            total_count = len(transactions)

            # Calculate total value
            total_value = sum(
                float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
                for tx in transactions
            )

            log(f"Transações encontradas: {total_count}")
            log(f"Total valor: R$ {total_value:.2f}")

            if transactions:
                log(f"\nPrimeiras 3 transações:")
                for i, tx in enumerate(transactions[:3], 1):
                    desc = tx.get("description", tx.get("name", ""))
                    valor = float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
                    account = tx.get("account", tx.get("account_type", tx.get("bank_type", "N/A")))
                    log(f"  {i}. {desc[:50]} | R$ {valor:.2f} | Conta: {account}")

            # Show available keys in the response
            if transactions:
                log(f"\nChaves disponíveis na transação:")
                keys = list(transactions[0].keys())
                log(f"  {', '.join(keys)}")
        else:
            log(f"Erro: {resp.status_code}")
            log(f"Resposta: {resp.text[:300]}")

    except Exception as e:
        log(f"Exceção: {type(e).__name__}: {e}")

log(f"\n{'=' * 100}")
log("FIM DO TESTE")
log(f"{'=' * 100}\n")

# Close the output file
output_file.close()
