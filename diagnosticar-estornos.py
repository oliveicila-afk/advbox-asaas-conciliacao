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

def advbox_api(method, path, data=None):
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

    status, resp = advbox_api("GET", f"/accounts/{ASAAS_ACCOUNT_ID}/transactions?date_range=2026-09-01,2026-09-30")

    if status != 200:
        log(f"❌ Erro ao listar transações: {status}")
        log(f"   Resposta: {resp}")
        return 1

    transactions = resp.get("data", []) if isinstance(resp, dict) else []
    log(f"✅ {len(transactions)} transações encontradas\n")

    # Procurar estornos
    log("Procurando estornos (debit entry_type):")
    estornos = []

    for i, t in enumerate(transactions, 1):
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
