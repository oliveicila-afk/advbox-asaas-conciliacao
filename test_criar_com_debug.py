#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test: Criar transação com debug detalhado do erro 422
"""

import os
import requests
import json

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")

ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

USER_ID = 65747
CATEGORY_ID = 70703
ASAAS_ACCOUNT_ID = 193264
COST_CENTER_ID = 60814

def formatar_valor_advbox(valor: float) -> str:
    """Format value for Advbox API (using comma as decimal separator)"""
    return f"{valor:.2f}".replace(".", ",")

if not ADVBOX_TOKEN:
    print("❌ ADVBOX_TOKEN not set")
    exit(1)

print("📝 Teste: Criar 1 transação com debug de erro")
print("=" * 80)

# Test payloads - try different variations
payloads = [
    {
        "name": "Original (com debit_account)",
        "payload": {
            "amount": formatar_valor_advbox(315.50),
            "date_due": "2026-09-01",
            "date_payment": "2026-09-01",
            "description": "TESTE - 09/01 Receita",
            "entry_type": "credit",
            "users_id": USER_ID,
            "categories_id": CATEGORY_ID,
            "debit_account": ASAAS_ACCOUNT_ID,
            "cost_centers_id": COST_CENTER_ID,
        }
    },
    {
        "name": "Sem cost_centers_id",
        "payload": {
            "amount": formatar_valor_advbox(315.50),
            "date_due": "2026-09-01",
            "date_payment": "2026-09-01",
            "description": "TESTE - 09/01 Receita",
            "entry_type": "credit",
            "users_id": USER_ID,
            "categories_id": CATEGORY_ID,
            "debit_account": ASAAS_ACCOUNT_ID,
        }
    },
    {
        "name": "Com account_id (não debit_account)",
        "payload": {
            "amount": formatar_valor_advbox(315.50),
            "date_due": "2026-09-01",
            "date_payment": "2026-09-01",
            "description": "TESTE - 09/01 Receita",
            "entry_type": "credit",
            "users_id": USER_ID,
            "categories_id": CATEGORY_ID,
            "account_id": ASAAS_ACCOUNT_ID,
            "cost_centers_id": COST_CENTER_ID,
        }
    },
]

headers = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "User-Agent": ADVBOX_USER_AGENT,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

for test in payloads:
    print(f"\n🧪 Testando: {test['name']}")
    print("-" * 80)

    print("\nPayload:")
    print(json.dumps(test['payload'], indent=2, ensure_ascii=False))

    try:
        resp = requests.post(
            f"{ADVBOX_BASE}/transactions",
            headers=headers,
            json=test['payload'],
            timeout=30
        )

        print(f"\n✓ Status: {resp.status_code}")

        if resp.text:
            try:
                data = resp.json()
                print("Response JSON:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except:
                print(f"Response text: {resp.text[:1000]}")

        if resp.status_code in (200, 201):
            print("✅ SUCESSO!")
        else:
            print(f"❌ ERRO: {resp.status_code}")

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
