#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico: Buscar estornos criados em erro
"""

import os
import sys
import requests
from datetime import datetime

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")
ASAAS_ACCOUNT_ID = 193264

ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def advbox_api(method, path, params=None, data=None):
    headers = {
        "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "User-Agent": ADVBOX_USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{ADVBOX_BASE}{path}"

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unknown method: {method}")

        resp.raise_for_status()
        return resp.status_code, resp.json() if resp.text else None
    except requests.exceptions.RequestException as e:
        try:
            error_data = e.response.json() if e.response.text else {"error": str(e)}
            return e.response.status_code if e.response else None, error_data
        except:
            return None, str(e)

def main():
    log("=" * 80)
    log("DIAGNÓSTICO: Buscar Estornos em Advbox")
    log("=" * 80)

    if not ADVBOX_TOKEN:
        log("❌ ERRO: ADVBOX_TOKEN não definido")
        return 1

    log(f"\nBuscando transações de setembro...")
    log(f"Conta ASAAS ID: {ASAAS_ACCOUNT_ID}")
    log("")

    # Try both endpoints
    log(f"Tentativa 1: /transactions endpoint...")
    status1, resp1 = advbox_api("GET", f"/transactions", {"limit": 1000, "offset": 0})

    log(f"Tentativa 2: /accounts/{ASAAS_ACCOUNT_ID}/transactions endpoint...")
    status2, resp2 = advbox_api("GET", f"/accounts/{ASAAS_ACCOUNT_ID}/transactions", {"limit": 1000, "offset": 0})

    # Use whichever endpoint works
    if status1 == 200:
        log(f"✅ /transactions funcionou (status {status1})")
        status, resp = status1, resp1
    elif status2 == 200:
        log(f"✅ /accounts/{ASAAS_ACCOUNT_ID}/transactions funcionou (status {status2})")
        status, resp = status2, resp2
    else:
        log(f"❌ Ambos endpoints falharam:")
        log(f"   /transactions: {status1}")
        log(f"   /accounts/{ASAAS_ACCOUNT_ID}/transactions: {status2}")
        return 1

    # Handle response format
    if isinstance(resp, dict):
        transactions = resp.get("data", []) if resp.get("data") else resp
    else:
        transactions = resp if isinstance(resp, list) else []

    log(f"\nTotal de transações retornadas: {len(transactions)}")

    # Show all transactions to help debug
    log("\nTodas as transações:")
    for i, t in enumerate(transactions, 1):
        log(f"{i}. {t.get('description', 'N/A')}")
        log(f"   - Data: {t.get('date_due') or t.get('date') or t.get('created_at') or 'N/A'}")
        log(f"   - Tipo: {t.get('entry_type', 'N/A')}")
        log(f"   - Valor: {t.get('amount', 'N/A')}")
        log(f"   - Conta Debit: {t.get('debit_account_id') or t.get('debit_account') or 'N/A'}")
        log("")

    # Filter transactions for ASAAS account and September 2026
    from datetime import datetime
    filtered_transactions = []
    for t in transactions:
        # Check if this transaction is for the ASAAS account
        debit_account = t.get("debit_account_id") or t.get("debit_account")
        date_str = t.get("date_due") or t.get("created_at") or t.get("date") or ""

        if date_str.startswith("2026-09"):
            # Accept if debit_account matches or if it's None (might be implicit)
            if debit_account == ASAAS_ACCOUNT_ID or debit_account == str(ASAAS_ACCOUNT_ID) or debit_account is None:
                filtered_transactions.append(t)

    log(f"✅ {len(filtered_transactions)} transações filtradas para setembro\n")

    # Procurar estornos
    log("Procurando estornos (debit entry_type):")
    estornos = []

    for i, t in enumerate(filtered_transactions, 1):
        entry_type = t.get("entry_type", "")
        description = t.get("description", "")
        amount = t.get("amount", "0")
        date_due = t.get("date_due", "")

        log(f"{i}. {description[:50]}")
        log(f"   Entry Type: {entry_type} | Amount: {amount} | Date: {date_due}")

        # Verificar se é um estorno esperado
        if entry_type == "debit":
            try:
                if isinstance(amount, str):
                    amt = float(amount.replace(",", "."))
                else:
                    amt = float(amount)

                if abs(amt - 11133.35) < 0.01 or abs(amt - 17558.66) < 0.01:
                    log(f"   ⚠️  ESTORNO ENCONTRADO!")
                    estornos.append({
                        "id": t.get("id"),
                        "amount": amt,
                        "description": description,
                    })
            except:
                pass
        log("")

    log("=" * 80)
    log(f"Resultado: {len(estornos)} estornos encontrados para deletar\n")

    if estornos:
        for e in estornos:
            log(f"✅ {e['description']}")
            log(f"   ID: {e['id']} | Valor: R$ {e['amount']:.2f}\n")
        return 0
    else:
        log("⚠️  Nenhum estorno encontrado")
        log("Possíveis razões:")
        log("  1. Já foram deletados")
        log("  2. ID da conta está incorreto")
        log("  3. Não existem em Advbox")
        return 0

if __name__ == "__main__":
    sys.exit(main())
