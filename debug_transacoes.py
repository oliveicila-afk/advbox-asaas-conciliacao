#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug script to check what's actually in Advbox
Run: ADVBOX_TOKEN="your_token" python3 debug_transacoes.py
"""

import os
import sys
import requests
import json

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
ASAAS_ACCOUNT_ID = 193264

if not ADVBOX_TOKEN:
    print("❌ ADVBOX_TOKEN não definido")
    print("Use: ADVBOX_TOKEN='seu_token' python3 debug_transacoes.py")
    sys.exit(1)

# Debug: validar token
print("=" * 80)
print("DEBUG: Validação de Token")
print("=" * 80)
print(f"✓ Token recebido: {len(ADVBOX_TOKEN)} caracteres")
print(f"✓ Primeiros 15 chars: {ADVBOX_TOKEN[:15]}...")
print(f"✓ Últimos 15 chars: ...{ADVBOX_TOKEN[-15:]}")
print(f"✓ Contém espaços? {'Sim' if ' ' in ADVBOX_TOKEN else 'Não'}")
print(f"✓ Contém quebras de linha? {'Sim' if chr(10) in ADVBOX_TOKEN else 'Não'}")

headers = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

print("\n" + "=" * 80)
print("DEBUG: Verificando transações em Advbox")
print("=" * 80)

# Test endpoint 1
print("\n1. Testando /transactions:")
try:
    resp = requests.get(f"{ADVBOX_BASE}/transactions", headers=headers, params={"limit": 50}, timeout=30)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        transactions = data.get("data", []) if isinstance(data, dict) else data
        print(f"   Transações encontradas: {len(transactions)}")

        # Filter for September
        sep_txns = [t for t in transactions if (t.get("date_due") or t.get("date") or "").startswith("2026-09")]
        print(f"   Transações em setembro: {len(sep_txns)}")

        # Show debit entries
        debits = [t for t in sep_txns if t.get("entry_type") == "debit"]
        print(f"   Chargebacks (debit): {len(debits)}")
        for d in debits:
            print(f"     - ID: {d.get('id')}")
            print(f"       Description: {d.get('description')}")
            print(f"       Amount: {d.get('amount')}")
            print(f"       Entry Type: {d.get('entry_type')}")
            print(f"       Date: {d.get('date_due') or d.get('date')}")
            print(f"       Debit Account: {d.get('debit_account_id') or d.get('debit_account')}")
            print()

        if sep_txns and len(sep_txns) <= 10:
            print("   Estrutura da primeira transação de setembro:")
            print(json.dumps(sep_txns[0], indent=2, ensure_ascii=False)[:500])
except Exception as e:
    print(f"   ❌ Erro: {e}")

# Test endpoint 2
print("\n2. Testando /accounts/{ASAAS_ACCOUNT_ID}/transactions:")
try:
    resp = requests.get(f"{ADVBOX_BASE}/accounts/{ASAAS_ACCOUNT_ID}/transactions", headers=headers, params={"limit": 50}, timeout=30)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        transactions = data.get("data", []) if isinstance(data, dict) else data
        print(f"   Transações encontradas: {len(transactions)}")

        # Filter for September
        sep_txns = [t for t in transactions if (t.get("date_due") or t.get("date") or "").startswith("2026-09")]
        print(f"   Transações em setembro: {len(sep_txns)}")

        # Show debit entries
        debits = [t for t in sep_txns if t.get("entry_type") == "debit"]
        print(f"   Chargebacks (debit): {len(debits)}")
        for d in debits:
            print(f"     - ID: {d.get('id')}")
            print(f"       Description: {d.get('description')}")
            print(f"       Amount: {d.get('amount')}")
            print(f"       Entry Type: {d.get('entry_type')}")
            print(f"       Date: {d.get('date_due') or d.get('date')}")
            print(f"       Debit Account: {d.get('debit_account_id') or d.get('debit_account')}")
            print()
except Exception as e:
    print(f"   ❌ Erro: {e}")

print("=" * 80)
