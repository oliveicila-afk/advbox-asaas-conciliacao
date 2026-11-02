#!/usr/bin/env python3
"""
Script para lançar as 10 TEDs recebidas do ASAAS no Advbox
Período: 01-10 de outubro de 2026
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional

# Dados das TEDs a lançar (será populado com dados do ASAAS)
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

class AsaasAPI:
    """Cliente para a API do ASAAS (buscar dados de faturas)"""

    BASE_URL = "https://api.asaas.com/v3"

    def __init__(self, api_key: str):
        """
        Inicializa o cliente da API do ASAAS

        Args:
            api_key: Chave de API do ASAAS
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "access_token": api_key,
            "Content-Type": "application/json"
        })

    def buscar_fatura(self, numero_fatura: str) -> Dict:
        """Busca uma fatura pelo número de referência"""
        response = self.session.get(
            f"{self.BASE_URL}/invoices",
            params={"reference": numero_fatura}
        )
        try:
            data = response.json() if response.text else {}
            if data.get("data"):
                return data["data"][0]  # Retorna primeira fatura encontrada
            return {}
        except:
            return {}


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
        customer_id: Optional[str] = None,
        process_id: Optional[str] = None,
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
            customer_id: ID do cliente (opcional)
            process_id: ID do processo (opcional)

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
            "payment_date": data,
            "description": f"TED recebida - Fatura {numero_referencia}",
        }

        # Adiciona cliente e processo se disponíveis
        if customer_id:
            payload["customer_id"] = customer_id
        if process_id:
            payload["process_id"] = process_id

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


def enriquecer_teds_com_asaas(teds: List[Dict], asaas_api_key: str) -> List[Dict]:
    """
    Enriquece os dados das TEDs com informações de cliente e processo do ASAAS

    Args:
        teds: Lista de TEDs
        asaas_api_key: Chave de API do ASAAS

    Returns:
        Lista de TEDs enriquecida
    """
    print("\n[*] Buscando dados de cliente e processo no ASAAS...")
    asaas = AsaasAPI(asaas_api_key)

    teds_enriquecidas = []
    for ted in teds:
        ted_enriquecida = ted.copy()
        fatura = asaas.buscar_fatura(ted['numero_fatura'])

        if fatura:
            # Extrai customer_id
            if 'customer' in fatura and fatura['customer']:
                ted_enriquecida['customer_id'] = fatura['customer'].get('id')
                print(f"  ✓ {ted['numero_fatura']}: cliente={ted_enriquecida.get('customer_id')}")

            # Extrai process_id (campo pode variar)
            if 'customFields' in fatura:
                for field in fatura.get('customFields', []):
                    if field.get('name', '').lower() in ['processo', 'process', 'process_id']:
                        ted_enriquecida['process_id'] = field.get('value')
                        print(f"  ✓ {ted['numero_fatura']}: processo={ted_enriquecida.get('process_id')}")
                        break
        else:
            print(f"  ⚠️  {ted['numero_fatura']}: não encontrada no ASAAS")

        teds_enriquecidas.append(ted_enriquecida)

    return teds_enriquecidas


def lançar_teds(api_key: str, asaas_api_key: str = None) -> None:
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

    # Enriquecer dados das TEDs com informações do ASAAS
    teds_processadas = TEDS
    if asaas_api_key:
        teds_processadas = enriquecer_teds_com_asaas(TEDS, asaas_api_key)

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

    for i, ted in enumerate(teds_processadas, 1):
        print(f"\n[{i}/{len(teds_processadas)}] Lançando TED {ted['numero_fatura']}...")
        print(f"  Valor: R$ {ted['valor']:,.2f}")
        print(f"  Data: {ted['data']}")
        if ted.get('customer_id'):
            print(f"  Cliente: {ted['customer_id']}")
        if ted.get('process_id'):
            print(f"  Processo: {ted['process_id']}")

        resultado = api.criar_transacao(
            valor=ted['valor'],
            data=ted['data'],
            numero_referencia=ted['numero_fatura'],
            users_id=users_id,
            debit_account=debit_account,
            categories_id=categories_id,
            cost_centers_id=cost_centers_id,
            customer_id=ted.get('customer_id'),
            process_id=ted.get('process_id'),
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
    print(f"Lançados com sucesso: {len(resultados['sucesso'])}/{len(teds_processadas)}")
    print(f"Com erro: {len(resultados['erro'])}/{len(teds_processadas)}")

    if resultados['sucesso']:
        print(f"\nTotal lançado: R$ {sum(t['valor'] for t in resultados['sucesso']):,.2f}")

    if resultados['erro']:
        print("\nTEDs com erro:")
        for ted in resultados['erro']:
            print(f"  - {ted['numero_fatura']}: {ted['erro']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    import sys

    # Obter as chaves de API
    if len(sys.argv) > 1:
        advbox_api_key = sys.argv[1]
    else:
        advbox_api_key = input("Digite a chave de API do Advbox: ")

    if not advbox_api_key:
        print("Erro: Chave de API do Advbox não fornecida")
        sys.exit(1)

    # ASAAS API key (opcional, para enriquecer dados)
    asaas_api_key = None
    if len(sys.argv) > 2:
        asaas_api_key = sys.argv[2]

    try:
        lançar_teds(advbox_api_key, asaas_api_key)
    except Exception as e:
        print(f"\nErro ao executar script: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
