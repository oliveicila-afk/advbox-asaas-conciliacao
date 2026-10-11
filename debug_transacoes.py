#!/usr/bin/env python3
import os
import requests
from datetime import datetime

ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "").strip()
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
TARGET_DATE = "2026-09-01"

print(f"Tokens definidos: ASAAS={bool(ASAAS_TOKEN)}, ADVBOX={bool(ADVBOX_TOKEN)}")
print(f"Data alvo: {TARGET_DATE}\n")

# Teste Asaas
print("=" * 80)
print("TESTE ASAAS")
print("=" * 80)

if ASAAS_TOKEN:
    headers = {"Authorization": f"Bearer {ASAAS_TOKEN}", "Accept": "application/json"}
    
    for income_type in ["PAYMENT_RECEIVED", "ANTICIPATED_RECEIVED"]:
        try:
            resp = requests.get(
                "https://api.asaas.com/v3/financialTransactions",
                headers=headers,
                params={
                    "startDate": TARGET_DATE,
                    "finishDate": TARGET_DATE,
                    "type": income_type,
                    "limit": 100,
                    "offset": 0,
                },
                timeout=10
            )
            
            print(f"\n{income_type}:")
            print(f"  Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"  Total encontrado: {len(data.get('data', []))}")
                print(f"  Resposta: {data}")
            else:
                print(f"  Erro: {resp.text[:200]}")
        except Exception as e:
            print(f"  Exception: {e}")
else:
    print("ASAAS_TOKEN não definido")

# Teste Advbox
print("\n" + "=" * 80)
print("TESTE ADVBOX")
print("=" * 80)

if ADVBOX_TOKEN:
    headers = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "Accept": "application/json"}
    
    try:
        resp = requests.get(
            "https://app.advbox.com.br/api/v1/transactions",
            headers=headers,
            params={
                "type": "income",
                "payment_date_from": TARGET_DATE,
                "payment_date_to": TARGET_DATE,
                "status": "paid",
                "per_page": 100,
                "page": 1,
            },
            timeout=10
        )
        
        print(f"\nStatus: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"Resposta JSON:")
            print(data)
        else:
            print(f"Erro: {resp.text[:200]}")
    except Exception as e:
        print(f"Exception: {e}")
else:
    print("ADVBOX_TOKEN não definido")
