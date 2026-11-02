#!/usr/bin/env python3
"""
Cria lançamentos no Advbox para cobranças recebidas (outubro 1-10, 2026)
Reutiliza centro de custo e categoria do histórico de cada cliente
"""

import os
import json
import requests
from datetime import datetime
from collections import Counter

class AdvboxAPI:
    BASE_URL = "https://api.advbox.com/v1"

    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })

    def buscar_clientes_por_nome(self, nome, limit=10):
        """Busca cliente por nome"""
        response = self.session.get(
            f"{self.BASE_URL}/people",
            params={"search": nome, "limit": limit},
            timeout=30
        )
        try:
            return response.json() if response.text else {}
        except:
            return {}

    def buscar_lancamentos_cliente(self, customer_id, limit=50):
        """Busca lançamentos históricos de um cliente"""
        response = self.session.get(
            f"{self.BASE_URL}/transactions",
            params={"customer": customer_id, "limit": limit},
            timeout=30
        )
        try:
            return response.json() if response.text else {}
        except:
            return {}

    def criar_lancamento(self, data):
        """Cria novo lançamento"""
        response = self.session.post(
            f"{self.BASE_URL}/transactions",
            json=data,
            timeout=30
        )
        try:
            return response.json() if response.text else {}
        except:
            return {}


# Lista de cobranças a lançar
COBRANCAS = [
    {"nome": "LUCINEY FREITAS PEREIRA", "fatura": "888808523", "valor": 102.04},
    {"nome": "ANDRESA MARIALVA TAVARES", "fatura": "924194084", "valor": 497.00},
    {"nome": "PRISCILA DE SOUZA ROSA BARRONCAS", "fatura": "678792460", "valor": 521.46},
    {"nome": "CLODOALDO DOS SANTOS BARBOZA", "fatura": "882981564", "valor": 400.00},
    {"nome": "ELIAS SOUZA CAMPOS", "fatura": "874869254", "valor": 935.00},
    {"nome": "Élida do Socorro Monte da Silva", "fatura": "636901058", "valor": 247.00},
    {"nome": "CRISTIANE ANTONIA DUARTE", "fatura": "924226650", "valor": 248.50},
    {"nome": "CELICE MEIRE SILVA DE FREITAS", "fatura": "924233025", "valor": 248.50},
    {"nome": "ORIVALDO DOS SANTOS BARBOSA JUNIOR", "fatura": "924292018", "valor": 248.50},
    {"nome": "ODILENE ROCHA DIAS", "fatura": "924301952", "valor": 248.50},
    {"nome": "VIVIANE DE OLIVEIRA MIRABAL", "fatura": "924633640", "valor": 67.00},
    {"nome": "VIVIANE DE OLIVEIRA MIRABAL", "fatura": "898199729", "valor": 67.00},
    {"nome": "SIMONE VILLANOVA", "fatura": "898672310", "valor": 248.50},
    {"nome": "GILBERTO LOPES DE ALMEIDA", "fatura": "900720982", "valor": 67.00},
    {"nome": "AMOS LOURENCO", "fatura": "900724421", "valor": 248.50},
    {"nome": "JENILSON MARINHO DA SILVA", "fatura": "901362283", "valor": 248.50},
    {"nome": "Deliene Siqueira Braga", "fatura": "849", "valor": 67.78},
    {"nome": "JOAO DO NASCIMENTO MORAES", "fatura": "927213426", "valor": 67.00},
    {"nome": "GILBERTO LOPES DE ALMEIDA", "fatura": "927213500", "valor": 67.00},
    {"nome": "FRANCIELY MESSIAS", "fatura": "928370038", "valor": 67.00},
    {"nome": "FRANCISCO MONTEIRO DE OLIVEIRA", "fatura": "784173106", "valor": 1246.66},
    {"nome": "DEBORA RENATA DE FREITAS BRAGA", "fatura": "834823523", "valor": 969.82},
    {"nome": "JOELMA MARTINS DOS SANTOS", "fatura": "8347", "valor": 73.81},
    {"nome": "ANDERSON MAIK MENDES", "fatura": "928756683", "valor": 400.00},
    {"nome": "JAIRA MARIA MACIEL SOUZA DA SILVA", "fatura": "901906054", "valor": 165.67},
    {"nome": "ROSIMARIO DE ARAGAO QUINTINO", "fatura": "902078451", "valor": 1500.00},
    {"nome": "MOISES FABIANO DA COSTA", "fatura": "902114710", "valor": 248.50},
    {"nome": "ZENI SOARES CAVALCANTE", "fatura": "902186118", "valor": 248.50},
    {"nome": "GISELLE DE OLIVEIRA LEITE", "fatura": "928999812", "valor": 248.50},
    {"nome": "ANDREA PAULA PINTO", "fatura": "929417093", "valor": 250.00},
    {"nome": "VALCINEIA BEZERRA GALVAO", "fatura": "887559930", "valor": 450.00},
    {"nome": "CALENE MULLER HAYEK", "fatura": "902791191", "valor": 129.90},
    {"nome": "FRANCIELY MESSIAS", "fatura": "902794129", "valor": 67.00},
    {"nome": "ROOSEWELT RODRIGUES DE LUCENA", "fatura": "902825894", "valor": 248.50},
    {"nome": "AUCIMAR CARNEIRO FIALHO", "fatura": "929980502", "valor": 497.00},
    {"nome": "VERA LUCIA SANTOS DA SILVA", "fatura": "930128523", "valor": 248.50},
    {"nome": "ANANDA MACIEL MAFRA", "fatura": "930616433", "valor": 282.99},
    {"nome": "VANDERLEY LOPES DA SILVA", "fatura": "870183120", "valor": 1000.00},
    {"nome": "SONIA MARIA BATISTA MONTEFUSCO", "fatura": "903523043", "valor": 248.50},
    {"nome": "ROBERTO ANTUNES DA SILVA", "fatura": "859293322", "valor": 35.00},
    {"nome": "Walquimar Vilaça Batista Borges", "fatura": "8307", "valor": 3.87},
    {"nome": "ROGER ROBSON BATISTA CARVALHO", "fatura": "852080842", "valor": 214.52},
    {"nome": "IGELVANIS DE SOUSA FILHA", "fatura": "931957287", "valor": 581.38},
    {"nome": "MIGUEL LUCIO BARBOSA CARMIN", "fatura": "720923709", "valor": 67.00},
    {"nome": "Maria Janete Xavier Pacheco", "fatura": "8566", "valor": 7.00},
    {"nome": "ANANDA MACIEL MAFRA", "fatura": "903996176", "valor": 282.99},
    {"nome": "RUTINEY AUGUSTA DE SOUZA", "fatura": "903996797", "valor": 248.50},
    {"nome": "WANESSA REIS FILGUEIRAS", "fatura": "904034277", "valor": 248.50},
    {"nome": "TALYSO WELISSON FALCAO OLIVEIRA", "fatura": "836241768", "valor": 892.04},
    {"nome": "EVANGELINA FERREIRA", "fatura": "932658929", "valor": 129.90},
    {"nome": "FABIO AMAZONAS MASSULO", "fatura": "932659106", "valor": 250.00},
    {"nome": "RODRIGO FERNANDES DE OLIVEIRA", "fatura": "932659611", "valor": 125.00},
    {"nome": "ESTER FIGUEIREDO ARAUJO", "fatura": "932660386", "valor": 248.50},
    {"nome": "JACIRENE MARTINS PENA", "fatura": "932660495", "valor": 187.50},
    {"nome": "RUTH VIEIRA LIMA", "fatura": "699051167", "valor": 679.66},
]


def extrair_centro_e_categoria(lancamentos):
    """Extrai centro de custo e categoria mais comuns do histórico"""
    centros = []
    categorias = []

    if isinstance(lancamentos, dict) and lancamentos.get('data'):
        for lanc in lancamentos['data']:
            if lanc.get('costCenter'):
                centros.append(lanc['costCenter'])
            if lanc.get('category'):
                categorias.append(lanc['category'])

    # Retorna o mais comum, ou None
    centro = Counter(centros).most_common(1)[0][0] if centros else None
    categoria = Counter(categorias).most_common(1)[0][0] if categorias else None

    return centro, categoria


if __name__ == "__main__":
    advbox_token = os.environ.get("ADVBOX_TOKEN", "").strip()
    if not advbox_token:
        print("Erro: ADVBOX_TOKEN não configurada")
        exit(1)

    advbox = AdvboxAPI(advbox_token)

    print(f"Processando {len(COBRANCAS)} cobranças...\n")

    sucessos = 0
    erros = 0

    for i, cobranca in enumerate(COBRANCAS, 1):
        print(f"[{i}/{len(COBRANCAS)}] {cobranca['nome']}...")

        try:
            # 1. Buscar cliente
            clientes = advbox.buscar_clientes_por_nome(cobranca['nome'])

            if not clientes.get('data') or len(clientes['data']) == 0:
                print(f"  ⚠ Cliente não encontrado no Advbox")
                erros += 1
                continue

            cliente = clientes['data'][0]
            cliente_id = cliente.get('id')

            # 2. Buscar histórico para extrair centro e categoria
            historico = advbox.buscar_lancamentos_cliente(cliente_id)
            centro, categoria = extrair_centro_e_categoria(historico)

            if not centro or not categoria:
                print(f"  ⚠ Sem histórico de centro/categoria para este cliente")
                erros += 1
                continue

            # 3. Criar novo lançamento
            novo_lancamento = {
                "customer": cliente_id,
                "value": cobranca['valor'],
                "description": f"Fatura {cobranca['fatura']}",
                "costCenter": centro,
                "category": categoria,
                "paymentDate": "2026-10-05",  # Exemplo: meio do período
                "status": "paid"
            }

            resultado = advbox.criar_lancamento(novo_lancamento)

            if resultado.get('id'):
                print(f"  ✓ Lançamento criado (ID: {resultado['id']})")
                sucessos += 1
            else:
                print(f"  ✗ Erro ao criar lançamento")
                erros += 1

        except Exception as e:
            print(f"  ✗ Erro: {str(e)}")
            erros += 1

    print(f"\n{'='*60}")
    print(f"Resumo: {sucessos} sucessos, {erros} erros")
    print(f"{'='*60}")
