#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analisar: Como Advbox armazena estornos/chargebacks nas transações existentes
"""

import os
import sys
import requests
import json
from datetime import datetime

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")

ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

ASAAS_ACCOUNT_ID = 193264

if not ADVBOX_TOKEN:
    print("❌ ADVBOX_TOKEN not set")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "User-Agent": ADVBOX_USER_AGENT,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

log("📊 Analisando estrutura de estornos em transações Advbox")
log("=" * 80)

# Query transactions for September
log("\n📋 Buscando transações de setembro (conta ASAAS)...")

try:
    # Try to get transactions for the ASAAS account
    url = f"{ADVBOX_BASE}/accounts/{ASAAS_ACCOUNT_ID}/transactions"
    resp = requests.get(url, headers=headers, params={"limit": 50}, timeout=30)

    log(f"Status: {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        transactions = data.get("data", [])

        log(f"\n✅ Encontradas {len(transactions)} transações")

        # Filter for September and look at structure
        sep_transactions = [t for t in transactions if "2026-09" in t.get("date", "")]

        if sep_transactions:
            log(f"\n📊 Transações de setembro (primeiras 10):")
            log("-" * 80)
            for i, t in enumerate(sep_transactions[:10]):
                log(f"\n  {i+1}. ID: {t.get('id')}")
                log(f"     Descrição: {t.get('description', '')}")
                log(f"     Tipo: {t.get('entry_type', 'N/A')}")
                log(f"     Valor: {t.get('amount', 'N/A')}")
                log(f"     Data: {t.get('date', 'N/A')}")
                log(f"     Categoria: {t.get('category_id', 'N/A')}")

                # Print full JSON for first transaction to see structure
                if i == 0:
                    log(f"\n     JSON completo (primeira transação):")
                    json_str = json.dumps(t, indent=6, ensure_ascii=False)
                    for line in json_str.split('\n')[:20]:
                        log(f"     {line}")
        else:
            log("\n⚠️  Nenhuma transação de setembro encontrada")
            log(f"\n   Analisando todas as transações para entender a estrutura:")
            if transactions:
                log(f"\n   Primeira transação (estrutura geral):")
                json_str = json.dumps(transactions[0], indent=6, ensure_ascii=False)
                for line in json_str.split('\n')[:30]:
                    log(f"   {line}")
    else:
        log(f"❌ Erro: {resp.status_code}")
        try:
            log(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        except:
            log(f"Response text: {resp.text[:200]}")

except Exception as e:
    log(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()

log("\n" + "=" * 80)
log("✅ Análise concluída")
