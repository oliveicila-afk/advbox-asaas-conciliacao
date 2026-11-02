#!/usr/bin/env python3
"""Debug: mostra a estrutura completa de uma fatura no ASAAS"""

import os
import sys
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

    # Debug da primeira fatura
    numero = "932787371"
    print(f"Buscando fatura: {numero}\n")

    fatura = asaas.buscar_fatura(numero)

    if not fatura:
        print("Não encontrada")
        sys.exit(1)

    print("=== ESTRUTURA COMPLETA ===\n")
    print(json.dumps(fatura, indent=2, ensure_ascii=False))
