#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test: Testar IDs de categorias diferentes para encontrar uma válida
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

def formatar_valor_advbox(valor: float) -> str:
    """Format value for Advbox API (using comma as decimal separator)"""
    return f"{valor:.2f}".replace(".", ",")

if not ADVBOX_TOKEN:
    print("❌ ADVBOX_TOKEN not set")
    exit(1)

print("🧪 Teste: Testar diferentes IDs de categorias")
print("=" * 80)

# Test different category IDs
# Based on the conciliar.py script, these are known to be used:
# 51: TAXAS_BANCARIAS
# 70703, 70704, 94787: Various fee categories (but these might not exist either)
# Try a range of common IDs
test_categories = [1, 2, 3, 5, 10, 51, 70703, 70704, 94787]

headers = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "User-Agent": ADVBOX_USER_AGENT,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

valid_categories = []

for cat_id in test_categories:
    print(f"\n🧪 Testando category_id: {cat_id}")
    print("-" * 80)

    payload = {
        "amount": formatar_valor_advbox(100.00),  # Test with R$ 100
        "date_due": "2026-10-09",
        "date_payment": "2026-10-09",
        "description": f"TESTE - Categoria ID {cat_id}",
        "entry_type": "credit",
        "users_id": USER_ID,
        "categories_id": cat_id,
        "debit_account": ASAAS_ACCOUNT_ID,
        "cost_centers_id": COST_CENTER_ID,
    }

    try:
        resp = requests.post(
            f"{ADVBOX_BASE}/transactions",
            headers=headers,
            json=payload,
            timeout=30
        )

        print(f"Status: {resp.status_code}")

        if resp.status_code in (200, 201):
            print(f"✅ SUCESSO! Category {cat_id} é válida!")
            valid_categories.append(cat_id)

            try:
                data = resp.json()
                print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
            except:
                pass
        else:
            print(f"❌ Erro {resp.status_code}")
            try:
                error = resp.json()
                print(f"Error: {json.dumps(error, indent=2, ensure_ascii=False)}")
            except:
                print(f"Response text: {resp.text[:200]}")

    except Exception as e:
        print(f"❌ Exception: {e}")

print("\n" + "=" * 80)
print(f"📊 RESUMO")
print("=" * 80)
if valid_categories:
    print(f"✅ Categorias válidas encontradas: {valid_categories}")
    print(f"\n💡 Use uma destas IDs para a reconciliação:")
    for cat_id in valid_categories:
        print(f"   - Category ID: {cat_id}")
else:
    print("❌ Nenhuma categoria válida encontrada!")
    print("   Verifique se o token ADVBOX_TOKEN está correto.")
