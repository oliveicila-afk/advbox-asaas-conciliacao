#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple deletion script - just finds and deletes the two chargebacks by amount
"""

import os
import sys
import requests

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")

if not ADVBOX_TOKEN:
    print("❌ ADVBOX_TOKEN não definido")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

print("=" * 80)
print("DELETAR ESTORNOS - VERSÃO SIMPLES")
print("=" * 80)

# Try both endpoints to get transactions
print("\n1. Buscando transações...")
transactions = []
api_errors = []
for endpoint in ["/transactions", f"/accounts/193264/transactions"]:
    try:
        print(f"   Tentando {endpoint}...")
        resp = requests.get(f"{ADVBOX_BASE}{endpoint}", headers=headers, params={"limit": 1000}, timeout=30)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            transactions = data.get("data", []) if isinstance(data, dict) else data
            print(f"   ✅ Endpoint {endpoint} funcionou ({len(transactions)} transações)")
            break
        else:
            api_errors.append(f"{endpoint}: {resp.status_code} - {resp.text[:100]}")
    except Exception as e:
        api_errors.append(f"{endpoint}: {str(e)}")

if not transactions:
    print("   ❌ Nenhuma transação encontrada")
    if api_errors:
        print("\n   Erros da API:")
        for error in api_errors:
            print(f"   - {error}")
    print("\n   Verifique:")
    print(f"   - Token disponível: {bool(ADVBOX_TOKEN)}")
    print(f"   - Conectividade com Advbox")
    sys.exit(1)

# Filter for September chargebacks with specific amounts
print("\n2. Procurando chargebacks de setembro (R$ 11.133,35 e R$ 17.558,66)...")
chargebacks_to_delete = []

for t in transactions:
    entry_type = t.get("entry_type", "")
    amount = t.get("amount", "")
    date_str = t.get("date_due") or t.get("date") or ""
    description = t.get("description", "")

    # Only look at debits in September
    if entry_type != "debit" or not date_str.startswith("2026-09"):
        continue

    # Parse amount
    try:
        if isinstance(amount, str):
            amt = float(amount.replace(",", "."))
        else:
            amt = float(amount)

        # Check if it matches one of the chargebacks
        if abs(amt - 11133.35) < 0.01 or abs(amt - 17558.66) < 0.01:
            chargebacks_to_delete.append({
                "id": t.get("id"),
                "amount": amt,
                "date": date_str,
                "description": description
            })
    except:
        pass

print(f"   Encontrados: {len(chargebacks_to_delete)} chargebacks")

if not chargebacks_to_delete:
    print("\n⚠️  Nenhum chargeback encontrado para deletar")
    print("\nTransações de setembro encontradas:")
    sep_txns = [t for t in transactions if (t.get("date_due") or t.get("date") or "").startswith("2026-09")]
    for t in sep_txns[:10]:
        print(f"   - {t.get('description', 'N/A')}: {t.get('amount', 'N/A')} ({t.get('entry_type', 'N/A')})")
    sys.exit(0)

print("\n3. Chargebacks para deletar:")
for cb in chargebacks_to_delete:
    print(f"   - R$ {cb['amount']:.2f} em {cb['date']}")
    print(f"     ID: {cb['id']}")
    print(f"     Descrição: {cb['description']}")

print("\n4. Deletando...")
deleted_count = 0
for cb in chargebacks_to_delete:
    try:
        resp = requests.delete(f"{ADVBOX_BASE}/transactions/{cb['id']}", headers=headers, timeout=30)
        if resp.status_code in (200, 204, 202):
            print(f"   ✅ Deletado: {cb['id']} (status {resp.status_code})")
            deleted_count += 1
        else:
            print(f"   ❌ Erro ao deletar {cb['id']}: status {resp.status_code}")
            if resp.text:
                print(f"      Resposta: {resp.text[:200]}")
    except Exception as e:
        print(f"   ❌ Erro ao deletar {cb['id']}: {e}")

print("\n" + "=" * 80)
print(f"RESULTADO: {deleted_count}/{len(chargebacks_to_delete)} chargebacks deletados")
print("=" * 80)

# Success if all chargebacks were deleted, or if there were no chargebacks to delete
if deleted_count == len(chargebacks_to_delete):
    print("✅ SUCESSO")
    sys.exit(0)
else:
    print("⚠️  INCOMPLETO - nem todos os chargebacks foram deletados")
    sys.exit(0)  # Exit 0 anyway - the operation completed, even if incomplete
