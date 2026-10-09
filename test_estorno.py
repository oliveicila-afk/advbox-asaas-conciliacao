#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test: Testar diferentes formas de enviar transações de estorno/chargeback
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
ASAAS_ACCOUNT_ID = 193264
COST_CENTER_ID = 60814
CATEGORY_ID = 1

def formatar_valor_advbox(valor: float) -> str:
    """Format value for Advbox API (using comma as decimal separator)"""
    return f"{valor:.2f}".replace(".", ",")

if not ADVBOX_TOKEN:
    print("❌ ADVBOX_TOKEN not set")
    exit(1)

print("🧪 Teste: Diferentes formas de criar estornos/chargebacks")
print("=" * 80)

headers = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "User-Agent": ADVBOX_USER_AGENT,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# Test 1: Negative amount with credit entry_type (current approach)
print("\n🧪 Teste 1: Negative amount com entry_type='credit'")
print("-" * 80)
payload1 = {
    "amount": formatar_valor_advbox(-100.00),
    "date_due": "2026-10-09",
    "date_payment": "2026-10-09",
    "description": "TESTE - Estorno com valor negativo e credit",
    "entry_type": "credit",
    "users_id": USER_ID,
    "categories_id": CATEGORY_ID,
    "debit_account": ASAAS_ACCOUNT_ID,
    "cost_centers_id": COST_CENTER_ID,
}

try:
    resp = requests.post(
        f"{ADVBOX_BASE}/transactions",
        headers=headers,
        json=payload1,
        timeout=30
    )
    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)[:500]}")
except Exception as e:
    print(f"❌ Exception: {e}")

# Test 2: Positive amount with debit entry_type
print("\n\n🧪 Teste 2: Positive amount com entry_type='debit'")
print("-" * 80)
payload2 = {
    "amount": formatar_valor_advbox(100.00),
    "date_due": "2026-10-09",
    "date_payment": "2026-10-09",
    "description": "TESTE - Estorno com valor positivo e debit",
    "entry_type": "debit",
    "users_id": USER_ID,
    "categories_id": CATEGORY_ID,
    "debit_account": ASAAS_ACCOUNT_ID,
    "cost_centers_id": COST_CENTER_ID,
}

try:
    resp = requests.post(
        f"{ADVBOX_BASE}/transactions",
        headers=headers,
        json=payload2,
        timeout=30
    )
    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)[:500]}")
except Exception as e:
    print(f"❌ Exception: {e}")

# Test 3: Negative amount with debit entry_type
print("\n\n🧪 Teste 3: Negative amount com entry_type='debit'")
print("-" * 80)
payload3 = {
    "amount": formatar_valor_advbox(-100.00),
    "date_due": "2026-10-09",
    "date_payment": "2026-10-09",
    "description": "TESTE - Estorno com valor negativo e debit",
    "entry_type": "debit",
    "users_id": USER_ID,
    "categories_id": CATEGORY_ID,
    "debit_account": ASAAS_ACCOUNT_ID,
    "cost_centers_id": COST_CENTER_ID,
}

try:
    resp = requests.post(
        f"{ADVBOX_BASE}/transactions",
        headers=headers,
        json=payload3,
        timeout=30
    )
    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)[:500]}")
except Exception as e:
    print(f"❌ Exception: {e}")

print("\n" + "=" * 80)
print("✅ Testes concluídos")
