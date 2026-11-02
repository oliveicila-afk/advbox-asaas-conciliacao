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

    def buscar_cobranca(self, numero_cobranca: str) -> Dict:
        """Busca uma cobrança pelo número de referência"""
        response = self.session.get(
            f"{self.BASE_URL}/payments",
            params={"reference": numero_cobranca}
        )
        try:
            data = response.json() if response.text else {}
            if data.get("data"):
                return data["data"][0]  # Retorna primeira cobrança encontrada
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
        self.processos_cache = {}
        self.categorias_cache = {}

    def buscar_processos(self) -> Dict:
        """Busca todos os processos e cria cache por número de processo"""
        if self.processos_cache:
            return self.processos_cache

        processos = []
        offset = 0

        while True:
            response = self.session.get(
                f"{self.BASE_URL}/lawsuits",
                params={"limit": 1000, "offset": offset}
            )

            if response.status_code != 200:
                print(f"  ⚠️  Erro ao buscar processos: {response.status_code}")
                break

            data = response.json().get("data", [])
            if not data:
                break

            processos.extend(data)
            offset += 1000
            time.sleep(2.2)

        # Cria cache indexado pelo número do processo
        for proc in processos:
            numero = proc.get("number", "").strip()
            if numero:
                self.processos_cache[numero] = proc

        return self.processos_cache

    def obter_configuracoes(self) -> Dict:
        """Obtém as configurações da conta (categories, etc)"""
        response = self.session.get(f"{self.BASE_URL}/settings")
        try:
            return response.json() if response.text else {}
        except:
            return {}

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
        # Tenta PUT primeiro (método padrão para atualização)
        response = self.session.put(
            f"{self.BASE_URL}/transactions/{transacao_id}",
            json=dados
        )

        if response.status_code in [200, 201]:
            return True, "Atualizado"
        else:
            try:
                erro = response.json().get("error", response.text)
            except:
                erro = response.text
            return False, str(erro)


def extrair_numero_processo_do_asaas(asaas_api: AsaasAPI, numero_cobranca: str) -> str:
    """
    Extrai o número do processo da cobrança no ASAAS (payments, não invoices)

    Procura em: judicialProcessNumber, externalIdentifier, customFields

    Returns:
        Número do processo ou "" se não encontrar
    """
    cobranca = asaas_api.buscar_cobranca(numero_cobranca)

    if not cobranca:
        return ""

    # Tenta campos diretos da cobrança
    campos_processo = [
        'judicialProcessNumber',
        'externalIdentifier',
        'lawNumber',
        'identifier',
        'processNumber',
        'numero_processo'
    ]

    for campo in campos_processo:
        valor = cobranca.get(campo, '')
        if isinstance(valor, str):
            valor = valor.strip()
        else:
            valor = str(valor) if valor else ''

        if valor and valor != '0' * len(valor):  # Ignora campos com apenas zeros
            return valor

    # Fallback: procura nos customFields
    for field in cobranca.get('customFields', []):
        field_name = field.get('name', '').lower()
        if field_name in ['processo', 'process', 'process_id', 'numero_processo', 'nº processo']:
            valor = field.get('value', '').strip()
            if valor:
                return valor

    return ""


def extrair_dados_do_processo_advbox(advbox_api: AdvboxAPI, numero_processo: str) -> Dict:
    """
    Busca o processo no Advbox e extrai cliente, tipo de ação, etc.

    Returns:
        Dict com: customers_id, customer_name, lawsuit_type, lawsuit_id
    """
    processos = advbox_api.buscar_processos()

    if numero_processo not in processos:
        return {}

    proc = processos[numero_processo]

    return {
        'lawsuit_id': proc.get('id', ''),
        'lawsuit_number': proc.get('number', ''),
        'lawsuit_type': proc.get('type', ''),  # Ex: "Ação Trabalhista | Reclamação"
        'customers_id': proc.get('customers', [{}])[0].get('id', '') if proc.get('customers') else '',
        'customer_name': proc.get('customers', [{}])[0].get('name', '') if proc.get('customers') else '',
    }


def extrair_categoria_por_tipo_acao(advbox_api: AdvboxAPI, lawsuit_type: str) -> str:
    """
    Mapeia o tipo de ação para a categoria correta no Advbox

    Returns:
        category_id ou "" se não encontrar
    """
    if not lawsuit_type:
        return ""

    config = advbox_api.obter_configuracoes()
    categories = config.get('financial', {}).get('categories', [])

    # Extrai a tese (parte após o |)
    partes = lawsuit_type.split('|')
    if len(partes) > 1:
        tese = partes[1].strip().upper()
    else:
        tese = partes[0].strip().upper()

    # Procura categoria que combine com a tese
    for cat in categories:
        category_name = cat.get('category', '').upper()
        if tese in category_name or category_name in tese:
            return str(cat.get('id', ''))

    return ""


def encontrar_lancamento(transacoes: List[Dict], numero_fatura: str) -> Dict:
    """
    Encontra o lançamento correspondente à fatura na lista de transações
    Procura pela descrição que contém "TED recebida - Fatura {numero_fatura}"
    """
    descricao_esperada = f"TED recebida - Fatura {numero_fatura}"

    for t in transacoes:
        desc = (t.get('description') or '')
        if descricao_esperada in desc or numero_fatura in desc:
            return t

    return {}


def atualizar_teds(advbox_api_key: str, asaas_api_key: str):
    """Main function"""
    print("=" * 60)
    print("Atualizando TEDs com cliente, processo e categoria do ASAAS")
    print("=" * 60)

    asaas = AsaasAPI(asaas_api_key)
    advbox = AdvboxAPI(advbox_api_key)

    # Busca todas as transações do Advbox
    print("\n[*] Buscando transações no Advbox...")
    transacoes = advbox.buscar_transacoes()
    print(f"    ✓ {len(transacoes)} transações encontradas")

    # Pré-carrega todos os processos do Advbox
    print("\n[*] Carregando processos do Advbox...")
    processos = advbox.buscar_processos()
    print(f"    ✓ {len(processos)} processos encontrados")

    # Processa cada TED
    resultados = {"sucesso": [], "erro": []}

    for i, ted in enumerate(TEDS, 1):
        numero_fatura = ted['numero_fatura']
        print(f"\n[{i}/{len(TEDS)}] Processando fatura {numero_fatura}...")

        # Busca número do processo no ASAAS
        print(f"  [*] Buscando informações no ASAAS...")
        numero_processo_asaas = extrair_numero_processo_do_asaas(asaas, numero_fatura)

        if not numero_processo_asaas:
            print(f"      ⚠️  Número do processo não encontrado no ASAAS")
            resultados['erro'].append({
                'numero_fatura': numero_fatura,
                'erro': 'Processo não encontrado no ASAAS'
            })
            continue

        print(f"      ✓ Processo no ASAAS: {numero_processo_asaas}")

        # Busca processo no Advbox
        print(f"  [*] Procurando processo no Advbox...")
        dados_processo = extrair_dados_do_processo_advbox(advbox, numero_processo_asaas)

        if not dados_processo:
            print(f"      ❌ Processo não encontrado no Advbox")
            resultados['erro'].append({
                'numero_fatura': numero_fatura,
                'erro': f'Processo {numero_processo_asaas} não encontrado no Advbox'
            })
            continue

        customers_id = dados_processo.get('customers_id', '')
        customer_name = dados_processo.get('customer_name', '')
        lawsuit_id = dados_processo.get('lawsuit_id', '')
        lawsuit_type = dados_processo.get('lawsuit_type', '')

        if customers_id:
            print(f"      ✓ Cliente: {customer_name} (ID: {customers_id})")
        else:
            print(f"      ❌ Cliente não encontrado")
            resultados['erro'].append({
                'numero_fatura': numero_fatura,
                'erro': 'Cliente não encontrado no processo'
            })
            continue

        if lawsuit_id:
            print(f"      ✓ Processo: {numero_processo_asaas} (ID: {lawsuit_id})")

        print(f"      ✓ Tipo de ação: {lawsuit_type}")

        # Extrai categoria baseada no tipo de ação
        category_id = extrair_categoria_por_tipo_acao(advbox, lawsuit_type)
        if category_id:
            print(f"      ✓ Categoria encontrada: {category_id}")
        else:
            print(f"      ⚠️  Categoria não encontrada")

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
        dados_atualizacao = {
            'customers_id': customers_id,
            'lawsuits_id': lawsuit_id,
        }

        if category_id:
            dados_atualizacao['categories_id'] = category_id

        # Atualiza no Advbox
        sucesso, mensagem = advbox.atualizar_transacao(lancamento_id, dados_atualizacao)

        if sucesso:
            print(f"  ✓ Atualizado com sucesso")
            resultados['sucesso'].append({
                'numero_fatura': numero_fatura,
                'customers_id': customers_id,
                'customer_name': customer_name,
                'lawsuit_id': lawsuit_id,
                'category_id': category_id
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
            print(f"  - {r['numero_fatura']}")
            print(f"    Cliente: {r['customer_name']} (ID: {r['customers_id']})")
            print(f"    Processo: {r['lawsuit_id']}")
            print(f"    Categoria: {r['category_id']}")

    if resultados['erro']:
        print("\nTEDs com erro:")
        for r in resultados['erro']:
            print(f"  - {r['numero_fatura']}: {r['erro']}")

    return resultados


if __name__ == "__main__":
    # Obter as chaves de API
    print(f"[DEBUG] sys.argv length: {len(sys.argv)}")

    if len(sys.argv) > 1:
        advbox_api_key = sys.argv[1].strip()
    else:
        advbox_api_key = input("Digite a chave de API do Advbox: ").strip()

    if not advbox_api_key:
        print("Erro: Chave de API do Advbox não fornecida")
        sys.exit(1)

    print(f"[DEBUG] Advbox OK")

    if len(sys.argv) > 2:
        asaas_api_key = sys.argv[2].strip()
    else:
        asaas_api_key = input("Digite a chave de API do ASAAS: ").strip()

    print(f"[DEBUG] ASAAS token received, length: {len(asaas_api_key)}")

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
