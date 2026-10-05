#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para lançar as transações faltantes em Advbox
Baseado na análise de divergência entre Asaas e Advbox (01-10 de setembro)

Transações a lançar:
- 09/01: R$ 248,50 (1 transação)
- 09/02: R$ 497,00 (1 transação)
- 09/03: R$ 815,50 (3 transações)
Total: R$ 1.561,00

NÃO lançar:
- Reversões (Estorno de transação via Pix) - 09/04 e 09/08
- Investimento (Lvmx) - 09/06
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from conciliar_v2 import advbox_post
except ImportError as e:
    print(f"Erro ao importar: {e}")
    sys.exit(1)

TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

print("\n" + "="*100)
print("📝 LANÇAMENTO DE TRANSAÇÕES FALTANTES EM ADVBOX")
print("="*100 + "\n")

# Dados das transações a lançar
# Formato: (data, valor, descrição_asaas, cliente)
transacoes_para_lancar = [
    # 09/01 - 1 transação
    ("2026-09-01", 248.50, "Cobrança recebida - fatura nr. 870788501", "MAZONIEL GUEDES REIS"),

    # 09/02 - 1 transação
    ("2026-09-02", 497.00, "Cobrança recebida - fatura nr. 897723169", "ANTONIO LOPES MARTINS DA MATA"),

    # 09/03 - 3 transações
    ("2026-09-03", 500.00, "Antecipação - fatura nr. 900261709", "ELCILENE DE SOUZA CARDOSO"),
    ("2026-09-03", 248.50, "Cobrança recebida - fatura nr. 901224705", "REGINA MARIA DE MATOS VIANA"),
    ("2026-09-03", 67.00, "Antecipação - fatura nr. 900720982", "GILBERTO LOPES DE ALMEIDA"),
]

total_valor = sum(float(tx[1]) for tx in transacoes_para_lancar)
print(f"Total de transações a lançar: {len(transacoes_para_lancar)}")
print(f"Valor total: R$ {total_valor:.2f}\n")

# ===== LANÇAR TRANSAÇÕES =====
print("📤 Iniciando lançamentos...\n")

lancamentos_sucesso = 0
lancamentos_erro = 0
ids_criados = []

for data, valor, descricao, cliente in transacoes_para_lancar:
    print(f"📍 {data} | R$ {valor:>8.2f} | {cliente[:40]:<40}")

    # Montar payload para Advbox
    payload = {
        "date_payment": data,
        "amount": float(valor),
        "description": f"{cliente} - {descricao}",
        "entry_type": "income",
        "category": "Contas a Receber",
    }

    # Enviar para Advbox
    resultado = advbox_post(payload)

    if resultado:
        tx_id = resultado.get("id", "???")
        print(f"   ✅ Lançado com sucesso (ID: {tx_id})\n")
        lancamentos_sucesso += 1
        ids_criados.append(tx_id)
    else:
        print(f"   ❌ ERRO ao lançar\n")
        lancamentos_erro += 1

# ===== RESUMO =====
print("\n" + "="*100)
print("📈 RESUMO DOS LANÇAMENTOS")
print("="*100 + "\n")

print(f"✅ Sucesso:  {lancamentos_sucesso}")
print(f"❌ Erro:     {lancamentos_erro}")
print(f"📊 Total:    {lancamentos_sucesso + lancamentos_erro}\n")

if lancamentos_sucesso > 0:
    print(f"💰 Valor total lançado: R$ {sum(float(tx[1]) for tx in transacoes_para_lancar[:lancamentos_sucesso]):.2f}\n")
    print(f"IDs criados: {', '.join(ids_criados)}\n")

print("="*100 + "\n")

if lancamentos_erro > 0:
    print("⚠️  Algumas transações não foram lançadas.\n")
    sys.exit(1)
else:
    print("✅ Todas as transações foram lançadas com sucesso!\n")
