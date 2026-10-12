#!/usr/bin/env python3
"""
Test API connections locally with the provided tokens.
Run this with: ASAAS_TOKEN="your_token" ADVBOX_TOKEN="your_token" python3 test_api_locally.py
"""

import os
import requests
import json

ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "").strip()
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()

def test_asaas():
    print("\n" + "="*80)
    print("🧪 TESTE ASAAS API")
    print("="*80)

    if not ASAAS_TOKEN:
        print("❌ ERRO: ASAAS_TOKEN não fornecido!")
        print("   Uso: ASAAS_TOKEN='seu_token' python3 test_api_locally.py")
        return False

    print(f"✅ ASAAS_TOKEN recebido (primeiros 10 chars): {ASAAS_TOKEN[:10]}...")

    headers = {
        "Authorization": f"Bearer {ASAAS_TOKEN}",
        "Accept": "application/json"
    }
    url = "https://api.asaas.com/v3/financialTransactions"
    params = {
        "startDate": "2026-09-01",
        "finishDate": "2026-09-01",
        "limit": 1
    }

    try:
        print(f"\n📍 URL: {url}")
        print(f"🔐 Headers: {{'Authorization': 'Bearer ...', 'Accept': 'application/json'}}")
        print(f"📋 Params: {params}")
        print(f"\n🔄 Enviando requisição...")

        response = requests.get(url, headers=headers, params=params, timeout=10)

        print(f"✓ Resposta recebida!")
        print(f"  Status Code: {response.status_code}")
        print(f"  Body (primeiros 300 chars): {response.text[:300]}")

        if response.status_code == 200:
            print(f"\n✅ TOKEN VÁLIDO! Conexão com Asaas estabelecida com sucesso")
            data = response.json()
            print(f"   Transações encontradas: {data.get('totalCount', 0)}")
            return True
        elif response.status_code == 401:
            print(f"\n❌ TOKEN INVÁLIDO ou EXPIRADO! (Status 401)")
            return False
        elif response.status_code == 403:
            print(f"\n❌ PERMISSÃO NEGADA! (Status 403)")
            return False
        else:
            print(f"\n⚠️  Status Inesperado: {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ ERRO na requisição: {str(e)}")
        return False

def test_advbox():
    print("\n" + "="*80)
    print("🧪 TESTE ADVBOX API")
    print("="*80)

    if not ADVBOX_TOKEN:
        print("❌ ERRO: ADVBOX_TOKEN não fornecido!")
        print("   Uso: ADVBOX_TOKEN='seu_token' python3 test_api_locally.py")
        return False

    print(f"✅ ADVBOX_TOKEN recebido (primeiros 10 chars): {ADVBOX_TOKEN[:10]}...")

    headers = {
        "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "Accept": "application/json"
    }
    url = "https://app.advbox.com.br/api/v1/transactions"
    params = {
        "limit": 1,
        "offset": 0
    }

    try:
        print(f"\n📍 URL: {url}")
        print(f"🔐 Headers: {{'Authorization': 'Bearer ...', 'Accept': 'application/json'}}")
        print(f"📋 Params: {params}")
        print(f"\n🔄 Enviando requisição...")

        response = requests.get(url, headers=headers, params=params, timeout=10)

        print(f"✓ Resposta recebida!")
        print(f"  Status Code: {response.status_code}")
        print(f"  Body (primeiros 300 chars): {response.text[:300]}")

        if response.status_code == 200:
            print(f"\n✅ TOKEN VÁLIDO! Conexão com Advbox estabelecida com sucesso")
            data = response.json()
            print(f"   Transações encontradas: {data.get('count', 0)}")
            return True
        elif response.status_code == 401:
            print(f"\n❌ TOKEN INVÁLIDO ou EXPIRADO! (Status 401)")
            return False
        elif response.status_code == 403:
            print(f"\n❌ PERMISSÃO NEGADA! (Status 403)")
            return False
        else:
            print(f"\n⚠️  Status Inesperado: {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ ERRO na requisição: {str(e)}")
        return False

if __name__ == "__main__":
    asaas_ok = test_asaas()
    advbox_ok = test_advbox()

    print("\n" + "="*80)
    print("📊 RESUMO")
    print("="*80)
    print(f"Asaas:  {'✅ OK' if asaas_ok else '❌ FALHOU'}")
    print(f"Advbox: {'✅ OK' if advbox_ok else '❌ FALHOU'}")

    if asaas_ok and advbox_ok:
        print("\n✅ TODOS OS TESTES PASSARAM!")
    else:
        print("\n❌ ALGUNS TESTES FALHARAM - Verifique seus tokens")
