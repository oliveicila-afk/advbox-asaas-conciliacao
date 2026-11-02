#!/usr/bin/env python3
"""
Atualiza os lançamentos de TEDs já criados no Advbox com as informações
de cliente e processo obtidas do ASAAS
"""

import os
import sys
import json
import time
import requests
from typing import Dict, List, Tuple

# Dados das TEDs a atualizar (mesmos números de fatura do lança_teds_advbox.py)
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
    """Cliente para a API do ASAAS"""

    BASE_URL = "https://api.asaas.com/v3"

    def __init__(self, api_key: str):
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
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def buscar_transacoes(self) -> List[Dict]:
        """Busca todas as transações"""
        transacoes = []
        offset = 0

        while True:
            response = self.session.get(
                f"{self.BASE_URL}/transactions",
                params={"limit": 1000, "offset": offset}
            )

            if response.status_code != 200:
                print(f"  ⚠️  Erro ao buscar transações: {response.status_code}")
                break

            data = response.json().get("data", [])
            if not data:
                break

            transacoes.extend(data)
            offset += 1000
            time.sleep(2.2)

        return transacoes

    def atualizar_transacao(self, transacao_id: int, dados: Dict) -> Tuple[bool, str]:
        """Atualiza uma transação com novos dados"""
        response = self.session.patch(
            f"{self.BASE_URL}/transactions/{transacao_id}",
            json=dados
        )

        if response.status_code == 200:
            return True, "Atualizado"
        else:
            try:
                erro = response.json().get("error", response.text)
            except:
                erro = response.text
            return False, str(erro)


def extrair_cliente_processo_do_asaas(asaas_api: AsaasAPI, numero_fatura: str) -> Tuple[str, str]:
    """
    Extrai customer_id e process_id da fatura no ASAAS

    Returns:
        Tupla (customer_id, process_id) ou ("", "") se não encontrar
    """
    fatura = asaas_api.buscar_fatura(numero_fatura)

    if not fatura:
        return "", ""

    customer_id = ""
    process_id = ""

    # Extrai customer_id
    if 'customer' in fatura and fatura['customer']:
        customer_id = fatura['customer'].get('id', '')

    # Extrai process_id dos customFields
    for field in fatura.get('customFields', []):
        if field.get('name', '').lower() in ['processo', 'process', 'process_id']:
            process_id = field.get('value', '')
            break

    return customer_id, process_id


def encontrar_lancamento(transacoes: List[Dict], numero_fatura: str) -> Dict:
    """
    Encontra o lançamento correspondente à fatura na lista de transações
    Procura pela descrição que contém "TED recebida - Fatura {numero_fatura}"
    """
    descricao_esperada = f"TED recebida - Fatura {numero_fatura}"

    for t in transacoes:
        desc = t.get('description', '')
        if descricao_esperada in desc or numero_fatura in desc:
            return t

    return {}


def atualizar_teds(advbox_api_key: str, asaas_api_key: str):
    """Main function"""
    print("=" * 60)
    print("Atualizando TEDs com cliente e processo do ASAAS")
    print("=" * 60)

    asaas = AsaasAPI(asaas_api_key)
    advbox = AdvboxAPI(advbox_api_key)

    # Busca todas as transações do Advbox
    print("\n[*] Buscando transações no Advbox...")
    transacoes = advbox.buscar_transacoes()
    print(f"    ✓ {len(transacoes)} transações encontradas")

    # Processa cada TED
    resultados = {"sucesso": [], "erro": []}

    for i, ted in enumerate(TEDS, 1):
        numero_fatura = ted['numero_fatura']
        print(f"\n[{i}/{len(TEDS)}] Processando fatura {numero_fatura}...")

        # Busca informações no ASAAS
        print(f"  [*] Buscando no ASAAS...")
        customer_id, process_id = extrair_cliente_processo_do_asaas(asaas, numero_fatura)

        if customer_id:
            print(f"      ✓ Cliente: {customer_id}")
        else:
            print(f"      ⚠️  Cliente não encontrado")

        if process_id:
            print(f"      ✓ Processo: {process_id}")
        else:
            print(f"      ⚠️  Processo não encontrado")

        # Encontra o lançamento no Advbox
        lancamento = encontrar_lancamento(transacoes, numero_fatura)

        if not lancamento:
            print(f"  ❌ Lançamento não encontrado no Advbox")
            resultados['erro'].append({
                'numero_fatura': numero_fatura,
                'erro': 'Lançamento não encontrado'
            })
            continue

        lancamento_id = lancamento.get('id')
        print(f"  [*] Atualizando lançamento (ID: {lancamento_id})...")

        # Prepara dados para atualização
        dados_atualizacao = {}

        if customer_id:
            dados_atualizacao['customers_id'] = customer_id

        if process_id:
            dados_atualizacao['lawsuits_id'] = process_id

        if not dados_atualizacao:
            print(f"  ⚠️  Nenhuma informação de cliente ou processo para atualizar")
            resultados['erro'].append({
                'numero_fatura': numero_fatura,
                'erro': 'Sem cliente e processo'
            })
            continue

        # Atualiza no Advbox
        sucesso, mensagem = advbox.atualizar_transacao(lancamento_id, dados_atualizacao)

        if sucesso:
            print(f"  ✓ Atualizado com sucesso")
            resultados['sucesso'].append({
                'numero_fatura': numero_fatura,
                'customer_id': customer_id,
                'process_id': process_id
            })
        else:
            print(f"  ❌ Erro na atualização: {mensagem}")
            resultados['erro'].append({
                'numero_fatura': numero_fatura,
                'erro': mensagem
            })

        time.sleep(2.2)  # Rate limiting

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"✓ Atualizados com sucesso: {len(resultados['sucesso'])}")
    print(f"❌ Com erro: {len(resultados['erro'])}")

    if resultados['sucesso']:
        print("\nAtualizações bem-sucedidas:")
        for r in resultados['sucesso']:
            print(f"  - {r['numero_fatura']}: cliente={r['customer_id']}, processo={r['process_id']}")

    if resultados['erro']:
        print("\nTEDs com erro:")
        for r in resultados['erro']:
            print(f"  - {r['numero_fatura']}: {r['erro']}")

    return resultados


if __name__ == "__main__":
    # Obter as chaves de API
    if len(sys.argv) > 1:
        advbox_api_key = sys.argv[1]
    else:
        advbox_api_key = input("Digite a chave de API do Advbox: ")

    if not advbox_api_key:
        print("Erro: Chave de API do Advbox não fornecida")
        sys.exit(1)

    if len(sys.argv) > 2:
        asaas_api_key = sys.argv[2]
    else:
        asaas_api_key = input("Digite a chave de API do ASAAS: ")

    if not asaas_api_key:
        print("Erro: Chave de API do ASAAS não fornecida")
        sys.exit(1)

    try:
        atualizar_teds(advbox_api_key, asaas_api_key)
    except Exception as e:
        print(f"\nErro ao executar script: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
