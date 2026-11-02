#!/usr/bin/env python3
"""
Script para verificar quais são as contas no Advbox
"""

import requests
import json
import sys

api_key = sys.argv[1]
base_url = "https://app.advbox.com.br/api/v1"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

session = requests.Session()
session.headers.update(headers)

# Obter configurações
print("Buscando contas no Advbox...")
response = session.get(f"{base_url}/settings")

try:
    data = response.json()
except:
    print("Erro ao parsear resposta. Status:", response.status_code)
    print("Resposta:", response.text[:500])
    sys.exit(1)

print("\n" + "=" * 60)
print("CONTAS BANCÁRIAS DISPONÍVEIS")
print("=" * 60)

banks = data.get("financial", {}).get("banks", [])
asaas_id = None

for bank in banks:
    bank_id = bank.get("id")
    bank_name = bank.get("name")
    print(f"ID: {bank_id} | Nome: {bank_name}")

    if "asaas" in bank_name.lower():
        asaas_id = bank_id
        print("  ⭐ ESTA É A CONTA ASAAS!")

print("\n" + "=" * 60)
if asaas_id:
    print(f"✓ Conta ASAAS encontrada com ID: {asaas_id}")
else:
    print("✗ Conta ASAAS NÃO foi encontrada!")
    print("Verifique o nome exato da conta no Advbox")
print("=" * 60)
