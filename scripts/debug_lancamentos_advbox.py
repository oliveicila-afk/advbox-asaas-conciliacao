#!/usr/bin/env python3
"""Debug: busca lançamentos no Advbox para os 10 TEDs"""

import os
import json
import requests

class AdvboxAPI:
    BASE_URL = "https://api.advbox.com/v1"

    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })

    def buscar_lancamentos_por_valor(self, valor, limit=50):
        """Busca lançamentos por valor"""
        # Busca na API de transações/lançamentos
        response = self.session.get(
            f"{self.BASE_URL}/transactions",
            params={"limit": limit},
            timeout=30
        )
        try:
            return response.json() if response.text else {}
        except:
            return {}


if __name__ == "__main__":
    advbox_token = os.environ.get("ADVBOX_TOKEN", "").strip()
    if not advbox_token:
        print("Erro: ADVBOX_TOKEN não configurada")
        exit(1)

    advbox = AdvboxAPI(advbox_token)

    # Os 10 valores do TED
    ted_values = [
        248.5,    # 924908121
        248.5,    # 925258116
        248.5,    # 926476598
        248.5,    # 928586680
        248.5,    # 928874986
        248.5,    # 929562005
        248.5,    # 929696991
        248.5,    # 929718746
        248.5,    # 930023237
        248.5,    # 932787371
    ]

    print("Buscando lançamentos no Advbox...\n")

    result = advbox.buscar_lancamentos_por_valor(248.5)

    if result.get('data'):
        lancamentos = result['data']
        print(f"Encontrados {len(lancamentos)} lançamentos:\n")

        for i, lanc in enumerate(lancamentos[:10], 1):
            print(f"[{i}] Lançamento:")
            print(f"    ID: {lanc.get('id')}")
            print(f"    Value: {lanc.get('value')}")
            print(f"    Description: {lanc.get('description')}")
            print(f"    Status: {lanc.get('status')}")
            print(f"    Customer: {lanc.get('customer')}")
            print(f"    Lawsuit: {lanc.get('lawsuit')}")
            print()
    else:
        print(f"Nenhum lançamento encontrado ou erro na API")
        print(f"\nResposta da API:")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:500])
