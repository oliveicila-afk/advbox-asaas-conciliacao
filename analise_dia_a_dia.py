#!/usr/bin/env python3
"""
Conciliação Diária — Asaas vs Advbox
Busca TODAS as receitas recebidas em uma data, compara e CORRIGE divergências.

REGRA OBRIGATÓRIA:
  Quando Asaas mostra um total X em um dia, Advbox DEVE ter EXATAMENTE X
  dos MESMOS clientes, MESMOS pagamentos, data CORRETA. Se não, corrige
  e continua tentando até ficarem iguais.

DUPLA CHECAGEM:
  Após cada correção, refaz a leitura de ambos os sistemas e valida se
  os totais batem EXATAMENTE. Só marca como "OK" quando estão iguais.

Uso via GitHub Actions (recomendado):
  Variáveis de ambiente injetadas pelos secrets do repositório:
    ASAAS_TOKEN, ADVBOX_TOKEN, TARGET_DATE

Uso local (apenas para testes):
  export ASAAS_TOKEN="seu_token"
  export ADVBOX_TOKEN="seu_token"
  export TARGET_DATE="2026-09-01"
  python3 analise_dia_a_dia.py
"""

import os
import requests
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import sys

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "").strip()
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
TARGET_DATE  = os.environ.get("TARGET_DATE", "2026-09-01").strip()
TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")

# Tipos de lançamento do Asaas que representam RECEITA recebida
ASAAS_INCOME_TYPES = ["PAYMENT_RECEIVED", "ANTICIPATED_RECEIVED"]

# Modo DRY-RUN: se True, mostra o que FARIA, sem executar as correções
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ["true", "1", "yes"]

# Configuração de reconciliação
MAX_RECONCILIATION_ATTEMPTS = 5
TOLERANCE = 0.01

# IDs de categorias para análise CAMADA 2 (categoria)
CATEGORIAS_HONORARIOS_INICIAIS = [51, 52, 53]
CATEGORIAS_HONORARIOS_EXITO = [54, 55, 56]
CATEGORIAS_HONORARIOS_INCUMBENCIAL = [57, 58]

# Cost centers para análise CAMADA 4 (origin)
COST_CENTER_ASAAS_PADRAO = 60814

# DEBUG: Ativa logging extremamente detalhado
DEBUG_MODE = os.environ.get("DEBUG_MODE", "true").lower() in ["true", "1", "yes"]

# ---------------------------------------------------------------------------
# FUNÇÕES DE CORREÇÃO — Advbox API Operations
# ---------------------------------------------------------------------------
def delete_advbox_transaction(tx_id: str, headers_advbox: dict) -> bool:
    """Remove uma transação do Advbox."""
    try:
        resp = requests.delete(
            f"https://app.advbox.com.br/api/v1/transactions/{tx_id}",
            headers=headers_advbox,
            timeout=30
        )
        if resp.status_code in [200, 204]:
            return True
        else:
            print(f"  ❌ Erro ao deletar {tx_id}: {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Erro ao deletar {tx_id}: {e}")
        return False


def create_advbox_transaction(asaas_tx: dict, headers_advbox: dict) -> bool:
    """Cria uma transação no Advbox baseada em uma transação do Asaas."""
    try:
        description = asaas_tx.get("description", "Pagamento Asaas")
        category_id = inferir_categoria(description)
        cost_center = COST_CENTER_ASAAS_PADRAO

        payload = {
            "type": "income",
            "description": description,
            "value": float(asaas_tx.get("value", 0)),
            "payment_date": TARGET_DATE,
            "status": "paid",
            "debit_bank": "ASAAS",
            "external_id": asaas_tx.get("id", ""),
            "categories_id": category_id,
            "cost_center": cost_center,
        }

        resp = requests.post(
            "https://app.advbox.com.br/api/v1/transactions",
            headers=headers_advbox,
            json=payload,
            timeout=30
        )

        if resp.status_code in [200, 201]:
            return True
        else:
            print(f"  ❌ Erro ao criar: {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Erro ao criar: {e}")
        return False


def inferir_categoria(description: str) -> int:
    """
    CAMADA 2: Infere a categoria de honorário baseado na descrição.
    """
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in ["êxito", "sucesso"]):
        return CATEGORIAS_HONORARIOS_EXITO[0]
    elif any(kw in desc_lower for kw in ["inicial", "protocolo", "entrada"]):
        return CATEGORIAS_HONORARIOS_INICIAIS[0]
    elif any(kw in desc_lower for kw in ["incumbencial", "mensal", "recursal"]):
        return CATEGORIAS_HONORARIOS_INCUMBENCIAL[0]
    return CATEGORIAS_HONORARIOS_INICIAIS[0]


def analisar_origin(tx: dict) -> str:
    """CAMADA 4: Infere a origem/cost center baseado nos dados da transação."""
    debit_bank = tx.get("debit_bank", "")
    if debit_bank == "ASAAS":
        return "ASAAS"
    return "MANUAL"


# ---------------------------------------------------------------------------
# FUNÇÕES REUTILIZÁVEIS DE LEITURA COM DEBUG
# ---------------------------------------------------------------------------
def fetch_asaas_transactions():
    """Busca todas as receitas do Asaas para TARGET_DATE com logging detalhado"""
    transactions = []
    headers_asaas = {
        "Authorization": f"Bearer {ASAAS_TOKEN}",
        "Accept": "application/json"
    }

    if DEBUG_MODE:
        print(f"\n[DEBUG ASAAS] Iniciando fetch para data: {TARGET_DATE}")
        print(f"[DEBUG ASAAS] Tipos de receita a buscar: {ASAAS_INCOME_TYPES}")

    for income_type in ASAAS_INCOME_TYPES:
        offset = 0
        limit = 100

        if DEBUG_MODE:
            print(f"\n[DEBUG ASAAS] === Tipo de receita: {income_type} ===")

        while True:
            try:
                if DEBUG_MODE:
                    print(f"[DEBUG ASAAS] Requisição: offset={offset}, limit={limit}")

                resp = requests.get(
                    "https://api.asaas.com/v3/financialTransactions",
                    headers=headers_asaas,
                    params={
                        "startDate": TARGET_DATE,
                        "finishDate": TARGET_DATE,
                        "type": income_type,
                        "limit": limit,
                        "offset": offset,
                    },
                    timeout=30
                )

                if DEBUG_MODE:
                    print(f"[DEBUG ASAAS] Status Code: {resp.status_code}")

                if resp.status_code != 200:
                    print(f"❌ Asaas ({income_type}): status {resp.status_code}")
                    if DEBUG_MODE:
                        print(f"[DEBUG ASAAS] Corpo da resposta de erro: {resp.text[:500]}")
                    break

                data = resp.json()

                if DEBUG_MODE:
                    print(f"[DEBUG ASAAS] Chaves da resposta: {list(data.keys())}")
                    print(f"[DEBUG ASAAS] hasMore: {data.get('hasMore', False)}")

                batch = data.get("data", [])

                if DEBUG_MODE:
                    print(f"[DEBUG ASAAS] Transações neste batch: {len(batch)}")
                    if batch:
                        print(f"[DEBUG ASAAS] Primeira transação (exemplo):")
                        print(f"  {json.dumps(batch[0], indent=2, default=str)}")

                transactions.extend(batch)

                has_more = data.get("hasMore", False)
                if not has_more or len(batch) == 0:
                    if DEBUG_MODE:
                        print(f"[DEBUG ASAAS] Fim da paginação para {income_type}")
                    break
                offset += limit

            except Exception as e:
                print(f"❌ Erro ao conectar Asaas ({income_type}): {e}")
                if DEBUG_MODE:
                    print(f"[DEBUG ASAAS] Exceção completa: {type(e).__name__}: {str(e)}")
                break

    if DEBUG_MODE:
        print(f"\n[DEBUG ASAAS] TOTAL FINAL: {len(transactions)} transações do Asaas")
        if transactions:
            print(f"[DEBUG ASAAS] Campos encontrados na primeira transação: {list(transactions[0].keys())}")

    return transactions


def fetch_advbox_transactions():
    """Busca todas as receitas do Advbox para TARGET_DATE e filtra com logging detalhado"""
    transactions = []
    headers_advbox = {
        "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "Accept": "application/json"
    }

    if DEBUG_MODE:
        print(f"\n[DEBUG ADVBOX] Iniciando fetch para data: {TARGET_DATE}")

    offset = 0
    limit = 100
    all_transactions_raw = []
    filtered_out_reasons = {
        "type_not_income": 0,
        "status_not_paid": 0,
        "debit_bank_not_asaas": 0,
        "date_mismatch": 0,
        "kept": 0,
    }

    while True:
        try:
            if DEBUG_MODE:
                print(f"\n[DEBUG ADVBOX] Requisição: offset={offset}, limit={limit}")

            resp = requests.get(
                "https://app.advbox.com.br/api/v1/transactions",
                headers=headers_advbox,
                params={
                    "limit": limit,
                    "offset": offset,
                },
                timeout=30
            )

            if DEBUG_MODE:
                print(f"[DEBUG ADVBOX] Status Code: {resp.status_code}")

            if resp.status_code != 200:
                print(f"❌ Advbox: status {resp.status_code}")
                if DEBUG_MODE:
                    print(f"[DEBUG ADVBOX] Corpo da resposta de erro: {resp.text[:500]}")
                break

            data = resp.json()

            if DEBUG_MODE:
                print(f"[DEBUG ADVBOX] Chaves da resposta: {list(data.keys())}")

            batch = data.get("data", []) or data.get("transactions", [])

            if DEBUG_MODE:
                print(f"[DEBUG ADVBOX] Transações neste batch (RAW): {len(batch)}")
                if batch:
                    print(f"[DEBUG ADVBOX] Primeira transação (exemplo):")
                    print(f"  {json.dumps(batch[0], indent=2, default=str)}")

            for tx_idx, tx in enumerate(batch):
                all_transactions_raw.append(tx)

                # Validações com logging
                tx_type = tx.get("type")
                if tx_type != "income":
                    filtered_out_reasons["type_not_income"] += 1
                    if DEBUG_MODE:
                        print(f"  [FILTRADO tx#{tx_idx}] type={tx_type} (esperava 'income')")
                    continue

                tx_status = tx.get("status")
                if tx_status != "paid":
                    filtered_out_reasons["status_not_paid"] += 1
                    if DEBUG_MODE:
                        print(f"  [FILTRADO tx#{tx_idx}] status={tx_status} (esperava 'paid')")
                    continue

                tx_debit_bank = tx.get("debit_bank")
                if tx_debit_bank != "ASAAS":
                    filtered_out_reasons["debit_bank_not_asaas"] += 1
                    if DEBUG_MODE:
                        print(f"  [FILTRADO tx#{tx_idx}] debit_bank={tx_debit_bank} (esperava 'ASAAS')")
                    continue

                payment_date = tx.get("payment_date", tx.get("date", ""))
                if payment_date and payment_date[:10] != TARGET_DATE:
                    filtered_out_reasons["date_mismatch"] += 1
                    if DEBUG_MODE:
                        print(f"  [FILTRADO tx#{tx_idx}] payment_date={payment_date} (esperava {TARGET_DATE})")
                    continue

                # Passou em todos os filtros
                filtered_out_reasons["kept"] += 1
                transactions.append(tx)
                if DEBUG_MODE:
                    print(f"  [MANTIDA tx#{tx_idx}] valor={tx.get('value', tx.get('amount', 0))}")

            if len(batch) < limit:
                if DEBUG_MODE:
                    print(f"[DEBUG ADVBOX] Fim da paginação (batch menor que limit)")
                break
            offset += limit

        except Exception as e:
            print(f"❌ Erro ao conectar Advbox: {e}")
            if DEBUG_MODE:
                print(f"[DEBUG ADVBOX] Exceção completa: {type(e).__name__}: {str(e)}")
            break

    if DEBUG_MODE:
        print(f"\n[DEBUG ADVBOX] === RESUMO DE FILTROS ===")
        print(f"  Total RAW (antes de filtros): {len(all_transactions_raw)}")
        print(f"  Removidas (type != 'income'): {filtered_out_reasons['type_not_income']}")
        print(f"  Removidas (status != 'paid'): {filtered_out_reasons['status_not_paid']}")
        print(f"  Removidas (debit_bank != 'ASAAS'): {filtered_out_reasons['debit_bank_not_asaas']}")
        print(f"  Removidas (data mismatch): {filtered_out_reasons['date_mismatch']}")
        print(f"  MANTIDAS (passa em todos filtros): {filtered_out_reasons['kept']}")
        print(f"[DEBUG ADVBOX] TOTAL FINAL: {len(transactions)} transações do Advbox")
        if transactions:
            print(f"[DEBUG ADVBOX] Campos encontrados na primeira transação: {list(transactions[0].keys())}")

    return transactions


# ---------------------------------------------------------------------------
# INÍCIO DO PROGRAMA
# ---------------------------------------------------------------------------
print("=" * 100)
print(f"CONCILIAÇÃO DIÁRIA — {TARGET_DATE}")
if DRY_RUN:
    print("(MODO DRY-RUN — sem executar correções)")
else:
    print("(MODO CORRETIVO — com dupla checagem)")
if DEBUG_MODE:
    print("(MODO DEBUG ATIVADO — logging extremamente detalhado)")
print("=" * 100)

if not ASAAS_TOKEN or not ADVBOX_TOKEN:
    print("\n❌ ERRO CRÍTICO: Tokens não fornecidos!")
    print(f"  ASAAS_TOKEN: {'✓ Definido' if ASAAS_TOKEN else '✗ FALTANDO'}")
    print(f"  ADVBOX_TOKEN: {'✓ Definido' if ADVBOX_TOKEN else '✗ FALTANDO'}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# LOOP PRINCIPAL DE RECONCILIAÇÃO COM DUPLA CHECAGEM
# ---------------------------------------------------------------------------
print(f"\n🔄 INICIANDO LOOP DE RECONCILIAÇÃO COM DUPLA CHECAGEM")
print(f"   Máximo de tentativas: {MAX_RECONCILIATION_ATTEMPTS}")
print("=" * 100)

headers_advbox = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "Accept": "application/json"
}

attempt = 0
reconciliation_complete = False
all_corrections = []
total_asaas_final = 0
total_advbox_final = 0

while attempt < MAX_RECONCILIATION_ATTEMPTS and not reconciliation_complete:
    attempt += 1
    print(f"\n{'='*100}")
    print(f"TENTATIVA {attempt}/{MAX_RECONCILIATION_ATTEMPTS}")
    print(f"{'='*100}")

    # Leitura 1: Buscar dados
    print(f"\n[LEITURA 1] Buscando transações...")
    asaas_transactions = fetch_asaas_transactions()
    advbox_transactions = fetch_advbox_transactions()

    total_asaas = sum(float(tx.get("value", 0)) for tx in asaas_transactions)
    total_advbox = sum(
        float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
        for tx in advbox_transactions
    )

    print(f"\n  Asaas:  {len(asaas_transactions)} transações | R$ {total_asaas:.2f}")
    print(f"  Advbox: {len(advbox_transactions)} transações | R$ {total_advbox:.2f}")

    # Matching
    print(f"\n[MATCHING] Identificando divergências...")

    def index_by_value(txs, value_key_fn):
        idx = {}
        for tx in txs:
            v = round(value_key_fn(tx), 2)
            idx.setdefault(v, []).append(tx)
        return idx

    asaas_idx = index_by_value(asaas_transactions, lambda tx: float(tx.get("value", 0)))
    advbox_idx = index_by_value(
        advbox_transactions,
        lambda tx: float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
    )

    matched = []
    unmatched_asaas = []
    remaining_advbox = {v: list(txs) for v, txs in advbox_idx.items()}

    for valor, asaas_list in asaas_idx.items():
        for asaas_tx in asaas_list:
            if valor in remaining_advbox and remaining_advbox[valor]:
                advbox_tx = remaining_advbox[valor].pop(0)
                matched.append((asaas_tx, advbox_tx, valor))
            else:
                unmatched_asaas.append(asaas_tx)

    unmatched_advbox = [tx for txs in remaining_advbox.values() for tx in txs]

    print(f"  Matches: {len(matched)}")
    print(f"  Faltando no Advbox: {len(unmatched_asaas)}")
    print(f"  Fantasmas no Advbox: {len(unmatched_advbox)}")

    # Executar correções
    if unmatched_advbox and not DRY_RUN:
        print(f"\n[CORRIGINDO] Removendo {len(unmatched_advbox)} transação(ões) fantasma(s)...")
        for tx in unmatched_advbox:
            valor = float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
            tx_id = tx.get("id", "")
            if tx_id:
                if delete_advbox_transaction(tx_id, headers_advbox):
                    all_corrections.append(("DELETE", valor))
                    print(f"  ✓ Removida: R$ {valor:.2f}")

    if unmatched_asaas and not DRY_RUN:
        print(f"\n[CORRIGINDO] Criando {len(unmatched_asaas)} transação(ões) faltante(s)...")
        for tx in unmatched_asaas:
            valor = float(tx.get("value", 0))
            if create_advbox_transaction(tx, headers_advbox):
                all_corrections.append(("CREATE", valor))
                print(f"  ✓ Criada: R$ {valor:.2f}")

    # DUPLA CHECAGEM: Relê os dados
    print(f"\n[DUPLA CHECAGEM] Relendo ambos os sistemas...")
    asaas_transactions_check = fetch_asaas_transactions()
    advbox_transactions_check = fetch_advbox_transactions()

    total_asaas_final = sum(float(tx.get("value", 0)) for tx in asaas_transactions_check)
    total_advbox_final = sum(
        float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
        for tx in advbox_transactions_check
    )

    diferenca = abs(total_asaas_final - total_advbox_final)

    print(f"\n  Asaas (dupla):  R$ {total_asaas_final:.2f}")
    print(f"  Advbox (dupla): R$ {total_advbox_final:.2f}")
    print(f"  Diferença: R$ {diferenca:.2f}")

    # Verificar se bateu
    if diferenca < TOLERANCE:
        print(f"\n✅ SUCESSO! Valores batem dentro da tolerância (R$ {TOLERANCE:.2f})")
        reconciliation_complete = True
    else:
        if attempt < MAX_RECONCILIATION_ATTEMPTS:
            print(f"\n⚠️  Valores ainda não batem. Tentando novamente...")
        else:
            print(f"\n❌ FALHA: Atingido limite de {MAX_RECONCILIATION_ATTEMPTS} tentativas")
            print(f"   Asaas: R$ {total_asaas_final:.2f}")
            print(f"   Advbox: R$ {total_advbox_final:.2f}")
            print(f"   Diferença: R$ {diferenca:.2f}")

# ---------------------------------------------------------------------------
# RESULTADO FINAL
# ---------------------------------------------------------------------------
print(f"\n{'='*100}")
print(f"RESULTADO FINAL DA RECONCILIAÇÃO")
print(f"{'='*100}")

if reconciliation_complete:
    print(f"\n✅ CONCILIAÇÃO COMPLETADA COM SUCESSO")
    print(f"   Tentativas: {attempt}/{MAX_RECONCILIATION_ATTEMPTS}")
    print(f"   Correções realizadas: {len(all_corrections)}")
    print(f"   Total Asaas: R$ {total_asaas_final:.2f}")
    print(f"   Total Advbox: R$ {total_advbox_final:.2f}")
    status_final = "✅ CONCILIADO"
else:
    print(f"\n❌ CONCILIAÇÃO NÃO COMPLETADA")
    print(f"   Tentativas: {attempt}/{MAX_RECONCILIATION_ATTEMPTS}")
    print(f"   Total Asaas: R$ {total_asaas_final:.2f}")
    print(f"   Total Advbox: R$ {total_advbox_final:.2f}")
    print(f"   Diferença pendente: R$ {abs(total_asaas_final - total_advbox_final):.2f}")
    status_final = f"❌ DIVERGÊNCIA: R$ {abs(total_asaas_final - total_advbox_final):.2f}"

# ---------------------------------------------------------------------------
# SALVAR RELATÓRIO JSON
# ---------------------------------------------------------------------------
report = {
    "data": TARGET_DATE,
    "gerado_em": datetime.now().isoformat(),
    "status": "CONCILIADO" if reconciliation_complete else "NAO_CONCILIADO",
    "tentativas": attempt,
    "max_tentativas": MAX_RECONCILIATION_ATTEMPTS,
    "totais_finais": {
        "asaas": round(total_asaas_final, 2),
        "advbox": round(total_advbox_final, 2),
        "diferenca": round(abs(total_asaas_final - total_advbox_final), 2),
    },
    "correcoes": {
        "total_realizadas": len(all_corrections),
        "detalhes": [
            {
                "tipo": corr[0],
                "valor": round(corr[1], 2)
            }
            for corr in all_corrections
        ],
    },
}

nome_arquivo = f"relatorio_{TARGET_DATE}.json"
with open(nome_arquivo, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"\n📄 Relatório salvo: {nome_arquivo}")
print(f"\n{status_final}\n")
