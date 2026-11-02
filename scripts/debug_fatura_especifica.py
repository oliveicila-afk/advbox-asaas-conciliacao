#!/usr/bin/env python3
"""Debug: busca uma cobrança específica para ver todos os campos"""

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

    def buscar_cobranca_por_reference(self, reference):
        """Busca cobrança por reference"""
        response = self.session.get(
            f"{self.BASE_URL}/payments",
            params={"reference": reference},
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

    numero = "932787371"
    print(f"Buscando cobrança com reference: {numero}\n")

    result = asaas.buscar_cobranca_por_reference(numero)

    if result.get("data"):
        cobranca = result["data"][0]
        print(json.dumps(cobranca, indent=2, ensure_ascii=False))
    else:
        print(f"Nenhuma cobrança encontrada com reference '{numero}'")
        print(f"\nResposta completa da API:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
