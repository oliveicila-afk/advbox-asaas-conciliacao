#!/usr/bin/env python3
"""
Debug script to test different Advbox account filter parameter names
and values to find the correct way to filter by ASAAS account.
"""

import os
import requests

ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
TARGET_DATE = "2026-09-01"

print("=" * 100)
print("TESTE DE FILTROS DE CONTA DO ADVBOX")
print("=" * 100)

if not ADVBOX_TOKEN:
    print("❌ ADVBOX_TOKEN não definido")
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
    print(f"\n\n{'=' * 100}")
    print(f"TESTE: {test['name']}")
    print(f"{'=' * 100}")

    try:
        resp = requests.get(
            "https://app.advbox.com.br/api/v1/transactions",
            headers=headers,
            params=test['params'],
            timeout=10
        )

        print(f"Status: {resp.status_code}")

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

            print(f"Transações encontradas: {total_count}")
            print(f"Total valor: R$ {total_value:.2f}")

            if transactions:
                print(f"\nPrimeiras 3 transações:")
                for i, tx in enumerate(transactions[:3], 1):
                    desc = tx.get("description", tx.get("name", ""))
                    valor = float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
                    account = tx.get("account", tx.get("account_type", tx.get("bank_type", "N/A")))
                    print(f"  {i}. {desc[:50]} | R$ {valor:.2f} | Conta: {account}")

            # Show available keys in the response
            if transactions:
                print(f"\nChaves disponíveis na transação:")
                keys = list(transactions[0].keys())
                print(f"  {', '.join(keys)}")
        else:
            print(f"Erro: {resp.status_code}")
            print(f"Resposta: {resp.text[:300]}")

    except Exception as e:
        print(f"Exceção: {type(e).__name__}: {e}")

print(f"\n{'=' * 100}")
print("FIM DO TESTE")
print(f"{'=' * 100}\n")
