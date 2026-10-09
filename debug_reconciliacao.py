#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug script para entender a estrutura dos dados do Advbox
"""

import os
import sys
import requests
import json
from datetime import datetime

# Configuration
ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")

ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

def log(msg):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def advbox_api(method, path, data=None):
    """Make API call to Advbox"""
    headers = {
        "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "User-Agent": ADVBOX_USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{ADVBOX_BASE}{path}"

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=data, timeout=30)
        else:
            raise ValueError(f"Unknown method: {method}")

        resp.raise_for_status()
        return resp.status_code, resp.json() if resp.text else None
    except requests.exceptions.RequestException as e:
        return None, str(e)

def main():
    log("=" * 80)
    log("DEBUG: Verificando estrutura de transações no Advbox")
    log("=" * 80)

    if not ADVBOX_TOKEN:
        log("❌ ERRO: ADVBOX_TOKEN não definido")
        sys.exit(1)

    # Try different query variations
    queries = [
        "/transactions?date_payment_from=2026-09-01&date_payment_to=2026-09-09&limit=10",
        "/transactions?account_id=193264&limit=10",
        "/transactions?limit=10",
    ]

    for i, query in enumerate(queries, 1):
        log(f"\n🔍 Query {i}: {query}")
        log("-" * 80)

        status, resp = advbox_api("GET", query)

        if status == 200:
            log(f"✅ Status 200")
            if resp:
                # Show structure
                data = resp.get("data", [])
                log(f"   Encontradas: {len(data)} transações")

                if data:
                    log(f"\n   Estrutura da primeira transação:")
                    first_tx = data[0]
                    for key in first_tx.keys():
                        val = first_tx[key]
                        # Truncate long values
                        if isinstance(val, str) and len(val) > 50:
                            val = val[:50] + "..."
                        log(f"      {key}: {val}")

                    # Show values for september
                    log(f"\n   Transações de Setembro 2026:")
                    september_txs = [
                        tx for tx in data
                        if tx.get("date_payment") and "2026-09" in tx.get("date_payment", "")
                    ]
                    log(f"      Total em setembro: {len(september_txs)}")

                    if september_txs:
                        total = sum(float(str(tx.get("amount", "0")).replace(",", ".")) for tx in september_txs)
                        log(f"      Soma: R$ {total:.2f}")

                        for tx in september_txs[:5]:  # Show first 5
                            date = tx.get("date_payment")
                            desc = tx.get("description") or "(sem desc)"
                            amount = tx.get("amount")
                            log(f"        {date} | {desc[:30]:30} | {amount}")
        else:
            log(f"❌ Status {status}")
            if resp:
                log(f"   Error: {resp}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
