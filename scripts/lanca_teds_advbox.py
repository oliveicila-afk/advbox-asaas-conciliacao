#!/usr/bin/env python3
"""
Script para lançar as 10 TEDs recebidas do ASAAS no Advbox
Período: 01-10 de outubro de 2026
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional

# Dados das TEDs a lançar
TEDS = [
    {"numero_fatura": "924908121", "valor": 27214.78, "data": "2026-10-01"},
    {"numero_fatura": "925258116", "valor": 6293.97, "data": "2026-10-02"},
    {"numero_fatura": "926476598", "valor": 8969.79, "data": "2026-10-03"},
    {"numero_fatura": "928586680", "valor": 20808.16, "data": "2026-10-04"},
    {"numero_fatura": "928874986", "valor": 7239.30, "data": "2026-10-05"},
    {"numero_fatura": "929562005", "valor": 9600.96, "data": "2026-10-06"},
    {"numero_fatura": "929696991", "valor": 8789.85, "data": "2026-10-07"},
    {"numero_fatura": "929718746", "valor": 17463.23, "data": "2026-10-08"},
    {"numero_fatura": "930023237", "valor": 11988.57, "data": "2026-10-09"},
    {"numero_fatura": "932787371", "valor": 4363.11, "data": "2026-10-10"},
]

class AdvboxAPI:
    """Cliente para a API do Advbox"""

    BASE_URL = "https://app.advbox.com.br/api/v1"

    def __init__(self, api_key: str):
        """
        Inicializa o cliente da API do Advbox

        Args:
            api_key: Chave de API do Advbox (obtida em Settings > Integrações)
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def obter_configuracoes(self) -> Dict:
        """Obtém as configurações da conta (users, contas, categorias, etc)"""
        response = self.session.get(f"{self.BASE_URL}/settings")
        try:
            return response.json() if response.text else {}
        except:
            return {"raw_response": response.text}

    def criar_transacao(
        self,
        valor: float,
        data: str,
        numero_referencia: str,
        users_id: int,
        debit_account: int,
        categories_id: int,
        cost_centers_id: int,
    ) -> Dict:
        """
        Cria um lançamento de transação no Advbox

        Args:
            valor: Valor da receita
            data: Data da transação (YYYY-MM-DD)
            numero_referencia: Número da fatura/referência
            users_id: ID do usuário responsável
            debit_account: ID da conta bancária
            categories_id: ID da categoria
            cost_centers_id: ID do centro de custo

        Returns:
            Resposta da API
        """
        # Formata o valor com vírgula (ex: 1.500,00)
        valor_formatado = f"{valor:,.2f}".replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")

        payload = {
            "users_id": users_id,
            "entry_type": "income",
            "debit_account": debit_account,
            "categories_id": categories_id,
            "cost_centers_id": cost_centers_id,
            "amount": valor_formatado,
            "date_due": data,
            "description": f"TED recebida - Fatura {numero_referencia}",
        }

        response = self.session.post(
            f"{self.BASE_URL}/transactions",
            json=payload
        )

        try:
            data = response.json() if response.text else {}
        except:
            data = {"raw_response": response.text}

        return {
            "status_code": response.status_code,
            "success": response.status_code in [200, 201],
            "data": data,
            "error": response.text if response.status_code not in [200, 201] else None
        }


def lançar_teds(api_key: str) -> None:
    """
    Lança todas as 10 TEDs no Advbox

    Args:
        api_key: Chave de API do Advbox
    """
    print("=" * 60)
    print("LANÇAMENTO DE TEDs NO ADVBOX")
    print("=" * 60)
    print(f"Total de TEDs: {len(TEDS)}")
    print(f"Período: 01-10 de outubro de 2026")
    print(f"Total a lançar: R$ {sum(ted['valor'] for ted in TEDS):,.2f}")
    print("=" * 60)

    api = AdvboxAPI(api_key)

    # Obter configurações
    print("\n[*] Obtendo configurações da conta...")
    config = api.obter_configuracoes()

    # Extrair IDs da primeira opção de cada categoria
    users_id = config.get("users", [{}])[0].get("id") if config.get("users") else None
    debit_account = config.get("financial", {}).get("banks", [{}])[0].get("id") if config.get("financial", {}).get("banks") else None
    categories_id = None
    cost_centers_id = config.get("financial", {}).get("cost_centers", [{}])[0].get("id") if config.get("financial", {}).get("cost_centers") else None

    # Procura por categoria de CRÉDITO
    for cat in config.get("financial", {}).get("categories", []):
        if cat.get("type") == "CRÉDITO":
            categories_id = cat.get("id")
            break

    if not all([users_id, debit_account, categories_id, cost_centers_id]):
        print("\n⚠️  Aviso: Não foi possível obter todos os IDs automaticamente:")
        print(f"  users_id: {users_id}")
        print(f"  debit_account: {debit_account}")
        print(f"  categories_id: {categories_id}")
        print(f"  cost_centers_id: {cost_centers_id}")
        print("\nContinuando com os IDs obtidos...")

    print(f"  users_id: {users_id}")
    print(f"  debit_account: {debit_account}")
    print(f"  categories_id: {categories_id}")
    print(f"  cost_centers_id: {cost_centers_id}")

    resultados = {
        "sucesso": [],
        "erro": []
    }

    for i, ted in enumerate(TEDS, 1):
        print(f"\n[{i}/{len(TEDS)}] Lançando TED {ted['numero_fatura']}...")
        print(f"  Valor: R$ {ted['valor']:,.2f}")
        print(f"  Data: {ted['data']}")

        resultado = api.criar_transacao(
            valor=ted['valor'],
            data=ted['data'],
            numero_referencia=ted['numero_fatura'],
            users_id=users_id,
            debit_account=debit_account,
            categories_id=categories_id,
            cost_centers_id=cost_centers_id,
        )

        if resultado['success']:
            print(f"  ✓ Sucesso!")
            resultados['sucesso'].append(ted)
        else:
            print(f"  ✗ Erro: {resultado['error']}")
            resultados['erro'].append({
                **ted,
                "erro": resultado['error']
            })

    # Resumo final
    print("\n" + "=" * 60)
    print("RESUMO DO LANÇAMENTO")
    print("=" * 60)
    print(f"Lançados com sucesso: {len(resultados['sucesso'])}/{len(TEDS)}")
    print(f"Com erro: {len(resultados['erro'])}/{len(TEDS)}")

    if resultados['sucesso']:
        print(f"\nTotal lançado: R$ {sum(t['valor'] for t in resultados['sucesso']):,.2f}")

    if resultados['erro']:
        print("\nTEDs com erro:")
        for ted in resultados['erro']:
            print(f"  - {ted['numero_fatura']}: {ted['erro']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    import sys

    # Obter a chave de API
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        api_key = input("Digite a chave de API do Advbox (obtida em Settings > Integrações): ")

    if not api_key:
        print("Erro: Chave de API não fornecida")
        sys.exit(1)

    try:
        lançar_teds(api_key)
    except Exception as e:
        print(f"\nErro ao executar script: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
