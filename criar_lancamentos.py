#!/usr/bin/env python3
"""
Script para criar lançamentos faltantes no Advbox
Cria as 8 receitas que existem no Asaas mas não no Advbox
Deleta as 4 entradas fantasmas criadas por erro
"""

import os
import json
import sys
import requests
from datetime import datetime

# Configuration
ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")

# User-Agent required to avoid Cloudflare blocking
ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

if not ADVBOX_TOKEN:
    print("❌ ERRO: ADVBOX_TOKEN não está definido")
    print("Use: ADVBOX_TOKEN='seu_token' python criar_lancamentos.py")
    sys.exit(1)

# Load analysis data
with open('analise_2026-09-09.json', 'r') as f:
    analise = json.load(f)

# Reference IDs (from conciliar.py - working values)
USER_ID = 65747  # USERS_ID_PRISCILA
CATEGORY_ID = 70703  # TAXA DE COMUNICAÇÃO (placeholder)
DEBIT_ACCOUNT_ID = 193264  # DEBIT_ACCOUNT_ASAAS
COST_CENTER_ID = 60814  # COST_CENTER_DESPESAS_FINANCEIRAS_GERAL

def log(msg):
    """Log with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def formatar_valor_advbox(valor: float) -> str:
    """
    Format value for Advbox API using comma (virgula) instead of dot
    due to a known bug in the API.
    """
    return f"{valor:.2f}".replace(".", ",")

def advbox_api(method, path, data=None):
    """Make API call to Advbox"""
    headers = {
        "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "User-Agent": ADVBOX_USER_AGENT,
        "Accept": "application/json"
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

        return resp.status_code, resp.json() if resp.text else None
    except Exception as e:
        return None, str(e)

def fetch_references():
    """Fetch reference IDs from Advbox"""
    global USER_ID, CATEGORY_ID, DEBIT_ACCOUNT_ID, COST_CENTER_ID

    log("🔍 Buscando referências no Advbox...")

    # Get users
    status, resp = advbox_api("GET", "/users")
    if status == 200 and resp and 'data' in resp and len(resp['data']) > 0:
        USER_ID = resp['data'][0].get('id')
        log(f"  ✓ USER_ID: {USER_ID}")
    else:
        log(f"  ❌ /users falhou: status={status}, resp={resp}")

    # Get categories
    status, resp = advbox_api("GET", "/categories")
    if status == 200 and resp and 'data' in resp and len(resp['data']) > 0:
        CATEGORY_ID = resp['data'][0].get('id')
        log(f"  ✓ CATEGORY_ID: {CATEGORY_ID}")
    else:
        log(f"  ❌ /categories falhou: status={status}, resp={resp}")

    # Get bank accounts (debit accounts)
    status, resp = advbox_api("GET", "/bank-accounts")
    if status == 200 and resp and 'data' in resp and len(resp['data']) > 0:
        DEBIT_ACCOUNT_ID = resp['data'][0].get('id')
        log(f"  ✓ DEBIT_ACCOUNT_ID: {DEBIT_ACCOUNT_ID}")
    else:
        log(f"  ❌ /bank-accounts falhou: status={status}, resp={resp}")

    # Get cost centers
    status, resp = advbox_api("GET", "/cost-centers")
    if status == 200 and resp and 'data' in resp and len(resp['data']) > 0:
        COST_CENTER_ID = resp['data'][0].get('id')
        log(f"  ✓ COST_CENTER_ID: {COST_CENTER_ID}")
    else:
        log(f"  ❌ /cost-centers falhou: status={status}, resp={resp}")

    if not all([USER_ID, CATEGORY_ID, DEBIT_ACCOUNT_ID, COST_CENTER_ID]):
        log("⚠️  ERRO: Nem todas as referências foram encontradas!")
        log(f"  USER_ID: {USER_ID}")
        log(f"  CATEGORY_ID: {CATEGORY_ID}")
        log(f"  DEBIT_ACCOUNT_ID: {DEBIT_ACCOUNT_ID}")
        log(f"  COST_CENTER_ID: {COST_CENTER_ID}")
        sys.exit(1)

def criar_lancamento(descricao, valor, data):
    """Create a transaction (lancamento) in Advbox"""
    log(f"Criando: {descricao} - R$ {valor:.2f}")

    payload = {
        "amount": formatar_valor_advbox(valor),
        "date_due": data,
        "date_payment": data,
        "description": descricao,
        "entry_type": "credit",
        "users_id": USER_ID,
        "categories_id": CATEGORY_ID,
        "debit_account": DEBIT_ACCOUNT_ID,
        "cost_centers_id": COST_CENTER_ID,
    }

    status, resp = advbox_api("POST", "/transactions", payload)

    if status in (200, 201):
        log(f"  ✓ Criado com sucesso")
        return resp.get('id') if isinstance(resp, dict) else None
    else:
        log(f"  ❌ Erro {status}: {resp}")
        return None

def deletar_lancamento(lancamento_id, descricao):
    """Delete a transaction from Advbox by marking it as canceled with PUT"""
    log(f"Deletando: {descricao} (ID: {lancamento_id})")

    # Advbox doesn't support DELETE method, so we mark as canceled/removed via PUT
    # Using status "deleted" or minimal payload to remove from accounting
    payload = {
        "status": "deleted",  # Mark as deleted/canceled
    }

    status, resp = advbox_api("PUT", f"/transactions/{lancamento_id}", payload)

    if status in (200, 201):
        log(f"  ✓ Cancelado com sucesso")
        return True
    else:
        log(f"  ❌ Erro {status}: {resp}")
        return False

def main():
    log("=" * 60)
    log("CRIAÇÃO DE LANÇAMENTOS FALTANTES - 2026-09-09")
    log("=" * 60)

    data_conciliacao = "2026-09-09"

    # Step 1: Create missing receitas
    log("\n📝 PASSO 1: Criando receitas faltando (8 itens)")
    log("-" * 60)

    receitas_criadas = 0
    for i, item in enumerate(analise['receita_faltando'], 1):
        asaas = item.get('asaas', {})
        descricao = asaas.get('description', '')
        valor = asaas.get('value', 0)

        lancamento_id = criar_lancamento(descricao, valor, data_conciliacao)
        if lancamento_id:
            receitas_criadas += 1

    log(f"\n✓ {receitas_criadas}/8 receitas criadas com sucesso")

    # Step 2: Delete phantom entries
    log("\n🗑️  PASSO 2: Deletando entradas fantasmas (4 itens)")
    log("-" * 60)

    fantasmas_deletados = 0
    for i, item in enumerate(analise['advbox_fantasmas'], 1):
        lancamento_id = item.get('id')
        descricao = item.get('description', '')

        if lancamento_id:
            if deletar_lancamento(lancamento_id, descricao):
                fantasmas_deletados += 1

    log(f"\n✓ {fantasmas_deletados}/4 entradas fantasmas deletadas")

    # Summary
    log("\n" + "=" * 60)
    log("RESUMO DA OPERAÇÃO")
    log("=" * 60)
    log(f"Receitas criadas: {receitas_criadas}/8")
    log(f"Fantasmas deletados: {fantasmas_deletados}/4")

    if receitas_criadas == 8 and fantasmas_deletados == 4:
        log("\n✅ SUCESSO! Reconciliação completada para 2026-09-09")
        return 0
    else:
        log(f"\n⚠️  ATENÇÃO: Nem todas as operações foram bem-sucedidas")
        return 1

if __name__ == "__main__":
    sys.exit(main())
