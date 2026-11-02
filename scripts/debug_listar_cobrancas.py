#!/usr/bin/env python3
"""Debug: lista as cobranças no ASAAS para entender a estrutura"""

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

    def listar_cobrancas(self, limit=10):
        """Lista as cobranças mais recentes"""
        response = self.session.get(
            f"{self.BASE_URL}/payments",
            params={"limit": limit},
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

    print("Listando 5 primeiras cobranças no ASAAS:\n")
    data = asaas.listar_cobrancas(5)

    if data.get("data"):
        for i, cobranca in enumerate(data["data"], 1):
            print(f"[{i}]")
            print(f"  ID: {cobranca.get('id')}")
            print(f"  Reference: {cobranca.get('reference')}")
            print(f"  Description: {cobranca.get('description')}")
            print(f"  Status: {cobranca.get('status')}")
            print(f"  JudicialProcessNumber: {cobranca.get('judicialProcessNumber')}")
            print(f"  ExternalIdentifier: {cobranca.get('externalIdentifier')}")
            print()
    else:
        print("Nenhuma cobrança encontrada")
