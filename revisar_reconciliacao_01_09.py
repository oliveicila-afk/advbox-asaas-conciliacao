#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REVISÃO PÓS-RECONCILIAÇÃO: Setembro 01-09 de 2026
==================================================

Script para verificar se as transações foram criadas corretamente
e se a reconciliação entre Asaas e Advbox está balanceada.
"""

import os
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# Configuration
ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")
ASAAS_BASE = "https://api.asaas.com/v3"
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "")
TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Fixed reference IDs
ASAAS_ACCOUNT_ID = 193264  # CONTA ASAAS
COST_CENTER_ID = 60814

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

def asaas_api(method, path, data=None):
    """Make API call to Asaas"""
    headers = {
        "access_token": ASAAS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{ASAAS_BASE}{path}"

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

def get_advbox_transactions(data_inicio, data_fim):
    """Fetch transactions from Advbox for date range"""
    # Query transactions between dates in ASAAS account
    path = (
        f"/transactions?"
        f"account_id={ASAAS_ACCOUNT_ID}&"
        f"date_payment_from={data_inicio}&"
        f"date_payment_to={data_fim}&"
        f"limit=500"
    )

    status, resp = advbox_api("GET", path)

    if status == 200 and resp:
        return resp.get("data", [])
    else:
        log(f"❌ Erro ao buscar transações Advbox: {status} - {resp}")
        return []

def main():
    log("=" * 80)
    log("REVISÃO PÓS-RECONCILIAÇÃO: Setembro 01-09 de 2026")
    log("=" * 80)

    if not ADVBOX_TOKEN:
        log("❌ ERRO: ADVBOX_TOKEN não definido")
        sys.exit(1)

    # Period to analyze: 01-09 September 2026
    data_inicio = "2026-09-01"
    data_fim = "2026-09-09"

    log(f"\n📊 Analisando período: {data_inicio} a {data_fim}")
    log(f"   Conta: ASAAS (ID: {ASAAS_ACCOUNT_ID})")
    log("=" * 80)

    # Get transactions from Advbox
    log("\n🔍 Buscando transações no Advbox...")
    transacoes_advbox = get_advbox_transactions(data_inicio, data_fim)

    if not transacoes_advbox:
        log("❌ Nenhuma transação encontrada")
        return 1

    log(f"✅ Encontradas {len(transacoes_advbox)} transações")

    # Calculate totals
    total_advbox = 0.0
    receitas = 0.0
    estornos = 0.0

    log("\n📋 Detalhes das transações:")
    log("-" * 80)

    for tx in transacoes_advbox:
        data = tx.get("date_payment", "")
        descricao = tx.get("description", "")

        # Parse amount (Advbox uses comma as decimal separator in response)
        amount_str = str(tx.get("amount", "0")).replace(",", ".")
        try:
            amount = float(amount_str)
        except:
            amount = 0.0

        # Classify
        if amount >= 0:
            receitas += amount
        else:
            estornos += amount

        total_advbox += amount

        log(f"  {data} | {descricao[:40]:40} | R$ {amount:>10.2f}")

    log("-" * 80)
    log(f"\n💰 RESUMO ADVBOX (01-09 setembro):")
    log(f"   Receitas:    R$ {receitas:>12.2f}")
    log(f"   Estornos:    R$ {estornos:>12.2f}")
    log(f"   TOTAL:       R$ {total_advbox:>12.2f}")

    # Expected totals (from previous analysis)
    log(f"\n📌 ESPERADO (conforme reconciliação planejada):")
    log(f"   01/09: R$ 315,50")
    log(f"   02/09: R$ 497,00")
    log(f"   03/09: R$ 815,50")
    log(f"   04/09: R$ 2.162,67 (receita) - R$ 11.133,35 (estorno)")
    log(f"   08/09: R$ 10.602,77 (receita) - R$ 17.558,66 (estorno)")

    expected_receitas = 315.50 + 497.00 + 815.50 + 2162.67 + 10602.77
    expected_estornos = -(11133.35 + 17558.66)
    expected_total = expected_receitas + expected_estornos

    log(f"\n   Total Receitas: R$ {expected_receitas:>12.2f}")
    log(f"   Total Estornos: R$ {expected_estornos:>12.2f}")
    log(f"   TOTAL ESPERADO: R$ {expected_total:>12.2f}")

    # Validation
    log(f"\n✅ VALIDAÇÃO:")
    diferenca = abs(total_advbox - expected_total)

    if diferenca < 0.01:
        log(f"   ✅ RECONCILIAÇÃO BEM-SUCEDIDA!")
        log(f"   Diferença: R$ {diferenca:.2f} (dentro da tolerância)")
        return 0
    else:
        log(f"   ⚠️  DIVERGÊNCIA DETECTADA")
        log(f"   Diferença: R$ {diferenca:.2f}")
        log(f"   Esperado: R$ {expected_total:.2f}")
        log(f"   Encontrado: R$ {total_advbox:.2f}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
