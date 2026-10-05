#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug: Obter TODAS as transações de Asaas para 09/08
Objetivo: Ver se realmente há apenas R$ 22.549,95 ou se há mais dados
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from conciliar_v2 import asaas_get_financial_transactions_do_dia
except ImportError as e:
    print(f"Erro ao importar: {e}")
    sys.exit(1)

TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

print("\n" + "="*100)
print("🔍 DEBUG ASAAS: Todas as transações de 09/08")
print("="*100 + "\n")

data = datetime(2026, 9, 8, tzinfo=tz).date()
data_str = data.isoformat()

try:
    print(f"📥 Buscando transações do Asaas para {data_str}...\n")
    items = asaas_get_financial_transactions_do_dia(data_str)

    print(f"✓ Total de transações: {len(items)}\n")

    if len(items) == 0:
        print("⚠️  NENHUMA transação encontrada!")
    else:
        print("="*100)
        print("TODAS AS TRANSAÇÕES (sem filtro)")
        print("="*100 + "\n")

        total_geral = 0
        por_tipo = {}

        for idx, item in enumerate(items, 1):
            tipo = item.get("type", "DESCONHECIDO")
            valor = float(item.get("value", 0) or 0)
            desc = item.get("description", "")[:60]

            print(f"{idx:3}. {tipo:30} | R$ {valor:>12.2f} | {desc}")

            total_geral += valor
            if tipo not in por_tipo:
                por_tipo[tipo] = {"count": 0, "total": 0}
            por_tipo[tipo]["count"] += 1
            por_tipo[tipo]["total"] += valor

        print("\n" + "="*100)
        print("RESUMO POR TIPO")
        print("="*100 + "\n")

        for tipo in sorted(por_tipo.keys()):
            dados = por_tipo[tipo]
            print(f"{tipo:30} | Qtd: {dados['count']:3} | Total: R$ {dados['total']:>12.2f}")

        print("\n" + "="*100)
        print(f"TOTAL GERAL: R$ {total_geral:,.2f}")
        print("="*100 + "\n")

        # Separa receitas e despesas
        print("ANÁLISE DE RECEITAS vs DESPESAS:\n")

        receitas = sum(float(i.get("value", 0) or 0) for i in items if float(i.get("value", 0) or 0) > 0)
        despesas = abs(sum(float(i.get("value", 0) or 0) for i in items if float(i.get("value", 0) or 0) < 0))

        print(f"  Receitas (valores positivos): R$ {receitas:>12.2f}")
        print(f"  Despesas (valores negativos):  R$ {despesas:>12.2f}")
        print(f"  Saldo líquido:                 R$ {receitas - despesas:>12.2f}\n")

except Exception as e:
    print(f"❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
