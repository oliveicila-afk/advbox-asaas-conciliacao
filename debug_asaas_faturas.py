#!/usr/bin/env python3
"""Debug: inspeciona a estrutura das faturas no ASAAS"""

import os
import sys
import json
import requests

TEDS = [
    "924908121", "925258116", "926476598", "928586680", "928874986",
    "929562005", "929696991", "929718746", "930023237", "932787371"
]

class AsaasAPI:
    BASE_URL = "https://api.asaas.com/v3"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "access_token": api_key,
            "Content-Type": "application/json"
        })

    def buscar_fatura(self, numero_fatura: str) -> dict:
        response = self.session.get(
            f"{self.BASE_URL}/invoices",
            params={"reference": numero_fatura}
        )
        try:
            data = response.json() if response.text else {}
            if data.get("data"):
                return data["data"][0]
            return {}
        except:
            return {}


if __name__ == "__main__":
    asaas_key = os.environ.get("ASAAS_CHAVE", "").strip()
    if not asaas_key:
        print("Erro: ASAAS_CHAVE não configurada")
        sys.exit(1)

    asaas = AsaasAPI(asaas_key)

    for numero in TEDS[:2]:  # Apenas primeiras 2 para debug
        print(f"\n{'='*60}")
        print(f"Fatura: {numero}")
        print('='*60)

        fatura = asaas.buscar_fatura(numero)

        if not fatura:
            print("Não encontrada")
            continue

        print(f"\nCampos principais:")
        for key in ["id", "reference", "customer", "description", "value", "status"]:
            if key in fatura:
                print(f"  {key}: {fatura[key]}")

        print(f"\nCustomFields:")
        custom_fields = fatura.get("customFields", [])
        if custom_fields:
            for field in custom_fields:
                print(f"  - {field.get('name')}: {field.get('value')}")
        else:
            print("  (vazio)")

        print(f"\nTodos os campos:")
        print(json.dumps(fatura, indent=2, ensure_ascii=False))
