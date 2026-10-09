#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DELETAR ESTORNOS CRIADOS EM ERRO
=================================

Os 2 estornos criados (R$ 11.133,35 em 09/04 e R$ 17.558,66 em 09/08)
não constam na lista de receitas fornecida pelo usuário.

A lista enviada é APENAS receita - sem despesas, sem chargebacks, sem estornos.

Estes estornos precisam ser removidos para corrigir a reconciliação.
"""

import os
import sys
import requests
from datetime import datetime
from typing import Optional, Dict, List

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")

ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

ASAAS_ACCOUNT_ID = 193264

def log(msg):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def advbox_api(method: str, path: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> tuple:
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
            resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unknown method: {method}")

        resp.raise_for_status()
        return resp.status_code, resp.json() if resp.text else None
    except requests.exceptions.RequestException as e:
        try:
            error_data = e.response.json() if e.response.text else {"error": str(e)}
            return e.response.status_code if e.response else None, error_data
        except:
            return None, str(e)

def listar_transacoes_setembro() -> List[Dict]:
    """List all transactions from ASAAS account for September 2026"""
    log("📋 Buscando transações de setembro na conta ASAAS (ID: 193264)...")

    # Fetch all transactions with pagination
    status, resp = advbox_api("GET", f"/transactions", {"limit": 1000, "offset": 0})

    if status == 200:
        # Handle response format
        if isinstance(resp, dict):
            all_transactions = resp.get("data", []) if resp.get("data") else resp
        else:
            all_transactions = resp if isinstance(resp, list) else []

        # Filter transactions for ASAAS account and September 2026
        transactions = []
        for t in all_transactions:
            # Check if this transaction is for the ASAAS account
            debit_account = t.get("debit_account_id")
            if debit_account == ASAAS_ACCOUNT_ID or debit_account == str(ASAAS_ACCOUNT_ID):
                # Check if date is in September 2026
                date_str = t.get("date_due") or t.get("created_at") or ""
                if date_str.startswith("2026-09"):
                    transactions.append(t)

        log(f"   ✅ Encontradas {len(transactions)} transações para conta ASAAS em setembro\n")
        return transactions
    else:
        log(f"   ❌ Erro ao listar transações: {status}")
        if isinstance(resp, dict):
            log(f"   Resposta: {resp}")
        return []

def encontrar_estornos_para_deletar(transacoes: List[Dict]) -> List[Dict]:
    """Find the chargebacks to delete"""
    estornos = []

    # Procurar por transações com entry_type="debit" (chargebacks) nas datas 09/04 e 09/08
    for t in transacoes:
        entry_type = t.get("entry_type", "")
        description = t.get("description", "")
        date_due = t.get("date_due", "")

        # Verificar se é um estorno (entry_type="debit" e descrição contém "Estorno")
        if entry_type == "debit" and "Estorno" in description:
            # Extrair valor (pode estar em string ou float)
            try:
                amount_str = t.get("amount", "0")
                if isinstance(amount_str, str):
                    amount = float(amount_str.replace(",", "."))
                else:
                    amount = float(amount_str)

                # Valores dos estornos esperados: 11133.35 (09/04) ou 17558.66 (09/08)
                if abs(amount - 11133.35) < 0.01 or abs(amount - 17558.66) < 0.01:
                    estornos.append({
                        "id": t.get("id"),
                        "description": description,
                        "amount": amount,
                        "date_due": date_due,
                        "entry_type": entry_type,
                    })
            except (ValueError, AttributeError):
                pass

    return estornos

def deletar_transacao(transaction_id: str, descricao: str, valor: float) -> bool:
    """Delete a single transaction"""
    log(f"  🗑️  Deletando: {descricao}")
    log(f"       Valor: R$ {valor:.2f} | ID: {transaction_id}")

    status, resp = advbox_api("DELETE", f"/transactions/{transaction_id}")

    if status in (200, 204, 202):
        log(f"    ✅ Deletado com sucesso (status {status})")
        return True
    else:
        error_msg = resp if isinstance(resp, dict) else str(resp)
        log(f"    ❌ Erro {status}: {error_msg}")
        return False

def main():
    log("=" * 80)
    log("DELETAR ESTORNOS CRIADOS EM ERRO")
    log("=" * 80)
    log("")
    log("CONTEXTO:")
    log("  • A lista de receitas enviada é APENAS receita (sem despesas/estornos)")
    log("  • 2 estornos foram criados em erro: R$ 11.133,35 (09/04) e R$ 17.558,66 (09/08)")
    log("  • Estes estornos NÃO constam em nenhum lugar da lista de receitas")
    log("  • Eles precisam ser REMOVIDOS para corrigir a reconciliação")
    log("")

    if not ADVBOX_TOKEN:
        log("❌ ERRO: ADVBOX_TOKEN não definido")
        log("")
        log("Como usar:")
        log("  ADVBOX_TOKEN='seu_token' python3 deletar_estornos_erro.py")
        log("")
        log("Ou via GitHub Actions (com secrets):")
        log("  - Crie uma workflow que execute este script")
        log("  - Configure ADVBOX_TOKEN como secret")
        sys.exit(1)

    # Listar transações e encontrar os estornos
    transacoes = listar_transacoes_setembro()

    if not transacoes:
        log("❌ Nenhuma transação encontrada em setembro")
        log("   Verifique se o token está correto e se há transações em Advbox")
        return 1

    # Encontrar os estornos a deletar
    estornos = encontrar_estornos_para_deletar(transacoes)

    log(f"📊 Análise das Transações:")
    log(f"   • Total de transações em setembro: {len(transacoes)}")
    log(f"   • Estornos encontrados para deletar: {len(estornos)}")
    log("")

    if not estornos:
        log("⚠️  Nenhum estorno encontrado para deletar")
        log("   Possíveis razões:")
        log("     1. Já foram deletados anteriormente")
        log("     2. ID da conta ASAAS está incorreto (esperado: 193264)")
        log("     3. A API não retorna essas transações")
        log("")
        log("Transações encontradas em setembro:")
        for i, t in enumerate(transacoes[:10], 1):
            log(f"   {i}. {t.get('description', 'N/A')} | "
                f"{t.get('amount', 'N/A')} | "
                f"Type: {t.get('entry_type', 'N/A')}")
        if len(transacoes) > 10:
            log(f"   ... e mais {len(transacoes) - 10} transações")
        return 0

    # Mostrar estornos encontrados
    log("Estornos encontrados:")
    for e in estornos:
        log(f"  • {e['description']}")
        log(f"    Valor: R$ {e['amount']:.2f} | Data: {e['date_due']} | ID: {e['id']}")
    log("")

    log("⚠️  ATENÇÃO:")
    log("   Esta operação vai DELETAR permanentemente estes estornos do Advbox")
    log("   Esta ação NÃO pode ser desfeita facilmente")
    log("")

    # Confirmation
    auto_confirm = "--auto" in sys.argv

    if not auto_confirm:
        print("❓ Deseja prosseguir com a deleção? (s/n): ", end="")
        resposta = input().strip().lower()

        if resposta != 's':
            log("\n❌ Operação cancelada pelo usuário")
            return 0
    else:
        log("⚡ Modo automático ativado - prosseguindo com deleção\n")

    # Deletar transações
    log("📝 DELETANDO TRANSAÇÕES...")
    log("=" * 80 + "\n")

    deletados = 0
    for estorno in estornos:
        if deletar_transacao(estorno["id"], estorno["description"], estorno["amount"]):
            deletados += 1

    # Summary
    log("\n" + "=" * 80)
    log("RESUMO DA OPERAÇÃO")
    log("=" * 80)
    log(f"✅ Transações deletadas: {deletados}/{len(estornos)}")

    if deletados == len(estornos) and deletados > 0:
        log("\n🎉 SUCESSO! Estornos removidos com sucesso")
        log("")
        log("💰 Reconciliação CORRIGIDA:")
        log("   • Receitas: R$ 14.393,44")
        log("     - 09/01: R$ 315,50")
        log("     - 09/02: R$ 497,00")
        log("     - 09/03: R$ 815,50")
        log("     - 09/04: R$ 2.162,67")
        log("     - 09/08: R$ 10.602,77")
        log("   • Estornos: NENHUM (removidos)")
        log("   • Total líquido: R$ 14.393,44")
        log("")
        log("📊 Próximos passos:")
        log("   1. Verificar saldo final na conta ASAAS em Advbox")
        log("   2. Confirmar que coincide com os dados de receita")
        log("   3. Atualizar a documentação de reconciliação")
        return 0
    else:
        log(f"\n⚠️  Apenas {deletados}/{len(estornos)} estornos foram deletados")
        log("   Verifique os erros acima")
        return 1

if __name__ == "__main__":
    sys.exit(main())
