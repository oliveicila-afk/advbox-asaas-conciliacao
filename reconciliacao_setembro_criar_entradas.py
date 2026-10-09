#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RECONCILIAÇÃO SETEMBRO 01-10: Criar Entradas Faltantes
=======================================================

Este script cria as transações faltantes identificadas entre Asaas e Advbox,
seguindo a regra OBRIGATÓRIA: todas as entradas devem estar na conta ASAAS

Regras de Reconciliação:
- Toda receita identificada em Asaas deve estar em Advbox na conta ASAAS
- Transações de investimento são EXCLUÍDAS da reconciliação
- Estornos/chargebacks devem ser contabilizados (negativamente)

Divergências Identificadas (01-10 Setembro):
- 09/01: R$ 315,50 (receitas)
- 09/02: R$ 497,00 (receitas)
- 09/03: R$ 815,50 (receitas)
- 09/04: R$ 13.296,02 (inclui R$ 11.133,35 estorno)
- 09/06: R$ 6.000,00 (INVESTIMENTO - EXCLUIR)
- 09/08: R$ 28.161,43 (inclui R$ 17.558,66 estorno)
- 09/05, 09/07, 09/09, 09/10: BALANCEADOS
"""

import os
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# Configuration
ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")
TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
tz = ZoneInfo(TIMEZONE)

ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Fixed reference IDs from working previous configurations
USER_ID = 65747  # Priscila
CATEGORY_ID = 70703  # Categoria padrão
ASAAS_ACCOUNT_ID = 193264  # CONTA ASAAS (OBRIGATÓRIA)
COST_CENTER_ID = 60814  # Centro de custo padrão

def log(msg):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def advbox_api(method, path, data=None):
    """Make API call to Advbox"""
    headers = {
        "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "User-Agent": ADVBOX_USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{ADVBOX_BASE}{path}"

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=data, timeout=30)
        elif method == "PUT":
            resp = requests.put(url, headers=headers, json=data, timeout=30)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unknown method: {method}")

        resp.raise_for_status()
        return resp.status_code, resp.json() if resp.text else None
    except requests.exceptions.RequestException as e:
        # Try to extract error details from response
        try:
            error_data = e.response.json() if e.response.text else {"error": str(e)}
            return e.response.status_code if e.response else None, error_data
        except:
            return None, str(e)

def formatar_valor_advbox(valor: float) -> str:
    """Format value for Advbox API (using comma as decimal separator)"""
    return f"{valor:.2f}".replace(".", ",")

def criar_lancamento(descricao: str, valor: float, data: str, category_id: int = None) -> bool:
    """
    Criar lançamento em Advbox na conta ASAAS

    OBRIGATÓRIO: debit_account = ASAAS_ACCOUNT_ID
    """
    log(f"  → Criando: {descricao[:60]} | R$ {valor:.2f} | {data}")

    cat_id = category_id if category_id else CATEGORY_ID
    payload = {
        "amount": formatar_valor_advbox(valor),
        "date_due": data,
        "date_payment": data,
        "description": descricao,
        "entry_type": "credit",  # Sempre "credit" - Advbox usa sinal do amount para devoluções
        "users_id": USER_ID,
        "categories_id": cat_id,
        "debit_account": ASAAS_ACCOUNT_ID,  # ⚠️ OBRIGATÓRIO
        "cost_centers_id": COST_CENTER_ID,
    }

    status, resp = advbox_api("POST", "/transactions", payload)

    if status in (200, 201):
        log(f"    ✅ Criado com sucesso (category_id={cat_id})")
        return True
    else:
        # Extract error message if available
        error_msg = resp if isinstance(resp, dict) else str(resp)
        log(f"    ❌ Erro {status}: {error_msg}")
        return False

def main():
    log("=" * 80)
    log("RECONCILIAÇÃO SETEMBRO 01-10: Criar Entradas Faltantes")
    log("=" * 80)

    if not ADVBOX_TOKEN:
        log("❌ ERRO: ADVBOX_TOKEN não definido")
        log("   Use: ADVBOX_TOKEN='token' python reconciliacao_setembro_criar_entradas.py")
        sys.exit(1)

    # Define transactions to create based on identified divergences
    # Following the reconciliation rules: ASAAS account only, exclude investments

    transacoes_para_criar = [
        # 09/01: R$ 315,50
        ("09/01 - Receita (Antecipação/Adiantamento)", 315.50, "2026-09-01"),

        # 09/02: R$ 497,00
        ("09/02 - Receita (Antecipação/Adiantamento)", 497.00, "2026-09-02"),

        # 09/03: R$ 815,50
        ("09/03 - Receita (Antecipação/Adiantamento)", 815.50, "2026-09-03"),

        # 09/04: R$ 13.296,02 (inclui estorno R$ 11.133,35)
        # Receita original
        ("09/04 - Receita Principal", 2162.67, "2026-09-04"),
        # Estorno/Chargeback (negativo)
        ("09/04 - Estorno/Chargeback", -11133.35, "2026-09-04"),

        # 09/06: R$ 6.000,00 - INVESTIMENTO (EXCLUÍDO conforme regras)
        # NÃO CRIAR

        # 09/08: R$ 28.161,43 (inclui estorno R$ 17.558,66)
        # Receita original
        ("09/08 - Receita Principal", 10602.77, "2026-09-08"),
        # Estorno/Chargeback (negativo)
        ("09/08 - Estorno/Chargeback", -17558.66, "2026-09-08"),
    ]

    log(f"\n📋 Preparado para criar {len(transacoes_para_criar)} entradas")
    log(f"   Conta: ASAAS (OBRIGATÓRIA)")
    log(f"   Período: 01-10 de Setembro de 2026\n")

    # Display summary
    log("Transações a serem criadas:")
    for desc, valor, data in transacoes_para_criar:
        log(f"  • {desc}: R$ {valor:>10.2f}")

    log("\n⚠️  ATENÇÃO:")
    log("   Esta operação vai CRIAR novas entradas no Advbox")
    log("   Todas as entradas serão criadas na conta ASAAS")
    log("   Valores negativos representam estornos/chargebacks")
    log("\n" + "=" * 80)

    # Confirmation
    auto_confirm = "--auto" in sys.argv

    if not auto_confirm:
        print("\n❓ Deseja prosseguir? (s/n): ", end="")
        resposta = input().strip().lower()

        if resposta != 's':
            log("\n❌ Operação cancelada pelo usuário")
            return 1
    else:
        log("\n⚡ Modo automático ativado - prosseguindo com reconciliação")

    # Create transactions
    log("\n📝 CRIANDO TRANSAÇÕES...")
    log("=" * 80 + "\n")

    criadas = 0
    for desc, valor, data in transacoes_para_criar:
        if criar_lancamento(desc, valor, data):
            criadas += 1

    # Summary
    log("\n" + "=" * 80)
    log("RESUMO DA OPERAÇÃO")
    log("=" * 80)
    log(f"✅ Transações criadas: {criadas}/{len(transacoes_para_criar)}")

    if criadas == len(transacoes_para_criar):
        log("\n🎉 SUCESSO! Reconciliação de setembro criada com sucesso")

        # Calculate new totals
        total_receitas = sum(v for _, v, _ in transacoes_para_criar if v > 0)
        total_estornos = sum(v for _, v, _ in transacoes_para_criar if v < 0)
        total_liquido = total_receitas + total_estornos

        log(f"\n💰 Totais criados:")
        log(f"   Receitas: R$ {total_receitas:>12.2f}")
        log(f"   Estornos: R$ {total_estornos:>12.2f}")
        log(f"   Líquido:  R$ {total_liquido:>12.2f}")

        log(f"\n📊 Próximos passos:")
        log(f"   1. Verificar as entradas criadas no Advbox")
        log(f"   2. Executar análise novamente para confirmar reconciliação")
        log(f"   3. Atualizar registros de auditoria")

        return 0
    else:
        log(f"\n⚠️  Apenas {criadas}/{len(transacoes_para_criar)} transações foram criadas")
        log("   Verifique os erros acima e tente novamente")
        return 1

if __name__ == "__main__":
    sys.exit(main())
