#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para lançar as transações faltantes em Advbox
Baseado na análise de divergência entre Asaas e Advbox (01-10 de setembro)

Transações a lançar:
- 09/01: R$ 315,50
- 09/02: R$ 497,00
- 09/03: R$ 815,50
Total: R$ 1.627,50

NÃO lançar:
- Reversões (Estorno de transação via Pix) - 09/04 e 09/08
- Investimento (Lvmx) - 09/06
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from conciliar_v2 import (
        asaas_get_financial_transactions_do_dia,
    )
except ImportError as e:
    print(f"Erro ao importar: {e}")
    sys.exit(1)

TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

# Configurações Advbox
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN")
if not ADVBOX_TOKEN:
    print("❌ Erro: ADVBOX_TOKEN não configurada")
    sys.exit(1)

ADVBOX_API_URL = "https://api.advbox.com.br/api/v1"
HEADERS = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "Content-Type": "application/json"}

print("\n" + "="*100)
print("📝 LANÇAMENTO DE TRANSAÇÕES FALTANTES EM ADVBOX")
print("="*100 + "\n")

# Dados das transações a lançar (extraídas manualmente da análise)
# Formato: (data, valor, descrição_asaas, cliente/fatura)
transacoes_para_lancar = [
    # 09/01
    ("2026-09-01", 248.50, "Cobrança recebida - fatura nr. 870788501", "MAZONIEL GUEDES REIS"),

    # 09/02
    ("2026-09-02", 497.00, "Cobrança recebida - fatura nr. 897723169", "ANTONIO LOPES MARTINS DA MATA"),

    # 09/03
    ("2026-09-03", 500.00, "Antecipação - fatura nr. 900261709", "ELCILENE DE SOUZA CARDOSO"),
    ("2026-09-03", 248.50, "Cobrança recebida - fatura nr. 901224705", "REGINA MARIA DE MATOS VIANA"),
    ("2026-09-03", 67.00, "Antecipação - fatura nr. 900720982", "GILBERTO LOPES DE ALMEIDA"),
]

print(f"Total de transações a lançar: {len(transacoes_para_lancar)}")
print(f"Valor total: R$ {sum(float(tx[1]) for tx in transacoes_para_lancar):.2f}\n")

# Função para criar transação em Advbox
def criar_lancamento_advbox(data, valor, descricao, cliente):
    """
    Cria um lançamento de RECEITA em Advbox
    """
    payload = {
        "date_payment": data,
        "amount": float(valor),
        "description": f"{cliente} - {descricao}",
        "entry_type": "income",  # Receita
        "category": "Contas a Receber",  # Categoria padrão
        "bank_account_id": None,  # Será preenchido automaticamente
    }

    try:
        response = requests.post(
            f"{ADVBOX_API_URL}/transactions",
            headers=HEADERS,
            json=payload,
            timeout=10
        )

        if response.status_code == 201:
            result = response.json()
            return True, result.get("id"), None
        else:
            return False, None, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, None, str(e)

# ===== LANÇAR TRANSAÇÕES =====
print("📤 Iniciando lançamentos...\n")

lancamentos_sucesso = 0
lancamentos_erro = 0
detalhes = []

for data, valor, descricao, cliente in transacoes_para_lancar:
    print(f"📍 {data} | R$ {valor:>8.2f} | {cliente[:40]:<40}")

    sucesso, tx_id, erro = criar_lancamento_advbox(data, valor, descricao, cliente)

    if sucesso:
        print(f"   ✅ Lançado com sucesso (ID: {tx_id})\n")
        lancamentos_sucesso += 1
        detalhes.append({
            "data": data,
            "valor": valor,
            "cliente": cliente,
            "status": "✅ Sucesso",
            "id": tx_id
        })
    else:
        print(f"   ❌ ERRO: {erro}\n")
        lancamentos_erro += 1
        detalhes.append({
            "data": data,
            "valor": valor,
            "cliente": cliente,
            "status": "❌ Erro",
            "id": None
        })

# ===== RESUMO =====
print("\n" + "="*100)
print("📈 RESUMO DOS LANÇAMENTOS")
print("="*100 + "\n")

print(f"✅ Sucesso:  {lancamentos_sucesso}")
print(f"❌ Erro:     {lancamentos_erro}")
print(f"📊 Total:    {lancamentos_sucesso + lancamentos_erro}\n")

if lancamentos_sucesso > 0:
    total_lancado = sum(float(tx[1]) for tx in transacoes_para_lancar[:lancamentos_sucesso])
    print(f"💰 Valor total lançado: R$ {total_lancado:.2f}\n")

print("="*100 + "\n")

if lancamentos_erro > 0:
    print("⚠️  Algumas transações não foram lançadas. Verifique os erros acima.\n")
    sys.exit(1)
else:
    print("✅ Todas as transações foram lançadas com sucesso!\n")
