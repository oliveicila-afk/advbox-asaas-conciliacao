#!/usr/bin/env python3
"""Debug: lista invoices de um customer para encontrar a que tem processo"""

import os
import json
import requests

class AsaasAPI:
    BASE_URL = "https://api.asaas.com/v3"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "access_token": api_key,
            "Content-Type": "application/json"
        })

    def listar_invoices(self, customer_id, limit=20):
        """Lista invoices de um customer"""
        response = self.session.get(
            f"{self.BASE_URL}/invoices",
            params={"customer": customer_id, "limit": limit},
            timeout=30
        )
        try:
            return response.json() if response.text else {}
        except:
            return {}


if __name__ == "__main__":
    asaas_key = os.environ.get("ASAAS_CHAVE", "").strip()
    if not asaas_key:
        print("Erro: ASAAS_CHAVE não configurada")
        exit(1)

    asaas = AsaasAPI(asaas_key)

    # Customer ID do payment anterior
    customer_id = "cus_000204399756"
    print(f"Listando invoices do customer: {customer_id}\n")

    result = asaas.listar_invoices(customer_id)

    if result.get('data'):
        invoices = result['data']
        print(f"Encontradas {len(invoices)} invoices:\n")

        for i, inv in enumerate(invoices, 1):
            print(f"[{i}] Invoice:")
            print(f"    ID: {inv.get('id')}")
            print(f"    Status: {inv.get('status')}")
            print(f"    Value: {inv.get('value')}")
            print(f"    Description: {inv.get('description')}")
            print(f"    Number: {inv.get('number')}")
            print(f"    ExternalReference: {inv.get('externalReference')}")
            print(f"    JudicialProcessNumber: {inv.get('judicialProcessNumber')}")
            print(f"    ExternalIdentifier: {inv.get('externalIdentifier')}")
            print()
    else:
        print("Nenhuma invoice encontrada")
        print(f"\nResposta da API:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
