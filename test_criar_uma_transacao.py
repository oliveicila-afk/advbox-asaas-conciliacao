#!/usr/bin/env python3
"""
Test: criar uma única transação de teste
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

def log_json(label, data):
    """Pretty print JSON"""
    print(f"\n{label}:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

if not ADVBOX_TOKEN:
    print("❌ ADVBOX_TOKEN not set")
    exit(1)

print("📝 Teste: Criar 1 transação")
print("=" * 60)

# Test payload
payload = {
    "amount": "315,50",  # 315.50 BRL
    "date_due": "2026-09-01",
    "date_payment": "2026-09-01",
    "description": "TESTE - 09/01 Receita",
    "entry_type": "credit",
    "users_id": USER_ID,
    "categories_id": CATEGORY_ID,
    "debit_account": ASAAS_ACCOUNT_ID,
    "cost_centers_id": COST_CENTER_ID,
}

log_json("Payload a enviar", payload)

headers = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "User-Agent": ADVBOX_USER_AGENT,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

print("\n🚀 Enviando POST /transactions...")
try:
    resp = requests.post(
        f"{ADVBOX_BASE}/transactions",
        headers=headers,
        json=payload,
        timeout=30
    )

    print(f"\n✓ Response Status: {resp.status_code}")

    if resp.text:
        try:
            data = resp.json()
            log_json("Response JSON", data)
        except:
            print(f"Response text: {resp.text[:500]}")
    else:
        print("(empty response)")

    if resp.status_code in (200, 201):
        print("\n✅ SUCESSO! Transação criada")
    else:
        print(f"\n❌ ERRO: Status {resp.status_code}")

except Exception as e:
    print(f"\n❌ Exception: {e}")
    import traceback
    traceback.print_exc()
