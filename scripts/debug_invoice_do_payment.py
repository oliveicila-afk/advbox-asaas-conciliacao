#!/usr/bin/env python3
"""Debug: busca a invoice de um payment para ver se tem os dados de processo"""

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

    def buscar_invoice(self, invoice_id):
        """Busca uma invoice específica"""
        response = self.session.get(
            f"{self.BASE_URL}/invoices/{invoice_id}",
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

    # Invoice ID do payment anterior
    invoice_id = "6g5s17vhbgg4jbu2"
    print(f"Buscando invoice: {invoice_id}\n")

    result = asaas.buscar_invoice(invoice_id)

    if result.get('id'):
        print("=" * 80)
        print("INVOICE ENCONTRADA - JSON COMPLETO:")
        print("=" * 80)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        print("\n" + "=" * 80)
        print("CAMPOS IMPORTANTES EXTRAÍDOS:")
        print("=" * 80)
        print(f"ID: {result.get('id')}")
        print(f"Status: {result.get('status')}")
        print(f"Description: {result.get('description')}")
        print(f"JudicialProcessNumber: {result.get('judicialProcessNumber')}")
        print(f"ExternalIdentifier: {result.get('externalIdentifier')}")

        print("\n" + "=" * 80)
        print("CUSTOM FIELDS (se existentes):")
        print("=" * 80)
        if result.get('customFields'):
            print(json.dumps(result.get('customFields'), indent=2, ensure_ascii=False))
        else:
            print("Nenhum customFields encontrado")

        print("\n" + "=" * 80)
        print("TODAS AS CHAVES DO OBJETO:")
        print("=" * 80)
        print(f"Chaves: {list(result.keys())}")
    else:
        print(f"Erro ou invoice não encontrada")
        print(f"Resposta da API:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
