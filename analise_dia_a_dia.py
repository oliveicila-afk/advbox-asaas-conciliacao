#!/usr/bin/env python3
"""
Conciliação Diária — Asaas vs Advbox
Busca TODAS as receitas recebidas em uma data, compara e CORRIGE divergências.
COM LOGGING MASSIVO EM ARQUIVO PARA DEBUG
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

ASAAS_INCOME_TYPES = ["PAYMENT_RECEIVED", "RECEIVABLE_ANTICIPATION_GROSS_CREDIT"]
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ["true", "1", "yes"]

MAX_RECONCILIATION_ATTEMPTS = 5
TOLERANCE = 0.01

CATEGORIAS_HONORARIOS_INICIAIS = [51, 52, 53]
CATEGORIAS_HONORARIOS_EXITO = [54, 55, 56]
CATEGORIAS_HONORARIOS_INCUMBENCIAL = [57, 58]
COST_CENTER_ASAAS_PADRAO = 60814

# LOGGING EM ARQUIVO
LOG_FILE = f"debug_{TARGET_DATE}.log"
def log_msg(msg, print_also=True):
    """Escreve em arquivo de log E opcionalmente na tela"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    if print_also:
        print(msg)

# Inicia log
open(LOG_FILE, "w").close()  # Limpa arquivo anterior
log_msg(f"{'='*100}\nINÍCIO DO LOG DE DEBUG\nData/Hora: {datetime.now()}\nTarget Date: {TARGET_DATE}\nDRY_RUN: {DRY_RUN}\n{'='*100}", True)

# Valida tokens
log_msg(f"\n[VALIDAÇÃO] ASAAS_TOKEN definido: {bool(ASAAS_TOKEN)}", True)
log_msg(f"[VALIDAÇÃO] ADVBOX_TOKEN definido: {bool(ADVBOX_TOKEN)}", True)

# ---------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------------------------
def inferir_categoria(description: str) -> int:
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in ["êxito", "sucesso"]):
        return CATEGORIAS_HONORARIOS_EXITO[0]
    elif any(kw in desc_lower for kw in ["inicial", "protocolo", "entrada"]):
        return CATEGORIAS_HONORARIOS_INICIAIS[0]
    elif any(kw in desc_lower for kw in ["incumbencial", "mensal", "recursal"]):
        return CATEGORIAS_HONORARIOS_INCUMBENCIAL[0]
    return CATEGORIAS_HONORARIOS_INICIAIS[0]


def delete_advbox_transaction(tx_id: str, headers_advbox: dict) -> bool:
    try:
        resp = requests.delete(
            f"https://app.advbox.com.br/api/v1/transactions/{tx_id}",
            headers=headers_advbox,
            timeout=30
        )
        success = resp.status_code in [200, 204]
        log_msg(f"  DELETE {tx_id}: {resp.status_code} - {'✓' if success else '❌'}", True)
        return success
    except Exception as e:
        log_msg(f"  ❌ Erro ao deletar {tx_id}: {e}", True)
        return False


def create_advbox_transaction(asaas_tx: dict, headers_advbox: dict) -> bool:
    try:
        description = asaas_tx.get("description", "Pagamento Asaas")
        category_id = inferir_categoria(description)
        payload = {
            "type": "income",
            "description": description,
            "value": float(asaas_tx.get("value", 0)),
            "payment_date": TARGET_DATE,
            "status": "paid",
            "debit_bank": "ASAAS",
            "external_id": asaas_tx.get("id", ""),
            "categories_id": category_id,
            "cost_center": COST_CENTER_ASAAS_PADRAO,
        }

        resp = requests.post(
            "https://app.advbox.com.br/api/v1/transactions",
            headers=headers_advbox,
            json=payload,
            timeout=30
        )

        success = resp.status_code in [200, 201]
        log_msg(f"  CREATE: {resp.status_code} - {'✓' if success else '❌'}", True)
        return success
    except Exception as e:
        log_msg(f"  ❌ Erro ao criar: {e}", True)
        return False


# ---------------------------------------------------------------------------
# FUNÇÕES DE LEITURA COM LOGGING MASSIVO
# ---------------------------------------------------------------------------
def fetch_asaas_transactions():
    """Busca Asaas com logging COMPLETO"""
    transactions = []
    headers_asaas = {
        "access_token": ASAAS_TOKEN,
        "Accept": "application/json"
    }

    log_msg(f"\n[ASAAS] Iniciando fetch", True)

    # Mesmo critério do workflow consultar-total-asaas: sem filtro "type" na API
    # (ele não filtra e duplicava os dados); filtra o tipo aqui e remove duplicados.
    all_raw = []
    offset = 0
    limit = 100
    while True:
        try:
            params = {"startDate": TARGET_DATE, "finishDate": TARGET_DATE, "limit": limit, "offset": offset}
            resp = requests.get("https://api.asaas.com/v3/financialTransactions",
                                headers=headers_asaas, params=params, timeout=30)
            log_msg(f"  Status: {resp.status_code}", True)
            if resp.status_code != 200:
                log_msg(f"  ERRO HTTP! Corpo: {resp.text[:500]}", True)
                break
            data = resp.json()
            batch = data.get("data", [])
            all_raw.extend(batch)
            if not data.get("hasMore", False) or len(batch) == 0:
                break
            offset += limit
        except Exception as e:
            log_msg(f"  ❌ EXCEÇÃO: {type(e).__name__}: {str(e)}", True)
            break

    from collections import Counter
    log_msg(f"[ASAAS] Bruto: {len(all_raw)} | tipos: {dict(Counter(t.get('type') for t in all_raw))}", True)
    vistos = set()
    for t in all_raw:
        if t.get("type") in ASAAS_INCOME_TYPES and t.get("id") not in vistos:
            vistos.add(t.get("id"))
            transactions.append(t)
    log_msg(f"[ASAAS] Receitas mantidas: {len(transactions)} | soma: {sum(float(t.get('value',0)) for t in transactions):.2f}", True)

    log_msg(f"\n[ASAAS] TOTAL: {len(transactions)} transações", True)
    return transactions


def fetch_advbox_transactions():
    """Busca Advbox com logging COMPLETO"""
    transactions = []
    headers_advbox = {
        "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    log_msg(f"\n[ADVBOX] Iniciando fetch", True)

    offset = 0
    limit = 100
    all_raw = []
    max_pages = 1000  # Limite máximo de páginas para não ficar puxando dados eternamente
    page_count = 0
    filter_counts = {
        "type_not_income": 0,
        "status_not_paid": 0,
        "debit_bank_not_asaas": 0,
        "date_mismatch": 0,
        "kept": 0,
    }

    while page_count < max_pages:
        try:
            params = {"limit": limit, "offset": offset}
            log_msg(f"  Requisição: offset={offset}, limit={limit}", False)

            resp = requests.get(
                "https://app.advbox.com.br/api/v1/transactions",
                headers=headers_advbox,
                params=params,
                timeout=30
            )

            log_msg(f"  Status: {resp.status_code}", True)
            log_msg(f"  Headers resposta: {dict(resp.headers)}", False)

            if resp.status_code != 200:
                log_msg(f"  ERRO HTTP! Corpo: {resp.text[:500]}", True)
                break

            data = resp.json()
            log_msg(f"  Chaves: {list(data.keys())}", True)
            log_msg(f"  Dados completos: {json.dumps(data, indent=2, default=str)}", False)

            batch = data.get("data", []) or data.get("transactions", [])
            log_msg(f"  Batch size (RAW): {len(batch)}", True)

            for idx, tx in enumerate(batch):
                all_raw.append(tx)
                tx_type = tx.get("type")
                tx_status = tx.get("status")
                tx_debit = tx.get("debit_bank")
                tx_date = tx.get("payment_date", tx.get("date", ""))

                log_msg(f"  TX[{idx}] type={tx_type} status={tx_status} debit_bank={tx_debit} date={tx_date}", False)

                if tx_type != "income":
                    filter_counts["type_not_income"] += 1
                    log_msg(f"    → FILTRADA (type)", False)
                    continue
                if tx_status != "paid":
                    filter_counts["status_not_paid"] += 1
                    log_msg(f"    → FILTRADA (status)", False)
                    continue
                if tx_debit != "ASAAS":
                    filter_counts["debit_bank_not_asaas"] += 1
                    log_msg(f"    → FILTRADA (debit_bank)", False)
                    continue
                if tx_date and tx_date[:10] != TARGET_DATE:
                    filter_counts["date_mismatch"] += 1
                    log_msg(f"    → FILTRADA (date)", False)
                    continue

                filter_counts["kept"] += 1
                transactions.append(tx)
                log_msg(f"    → MANTIDA", False)

            page_count += 1

            if len(batch) < limit:
                log_msg(f"  Fim da paginação", True)
                break
            offset += limit

        except Exception as e:
            log_msg(f"  ❌ EXCEÇÃO: {type(e).__name__}: {str(e)}", True)
            break

    log_msg(f"\n[ADVBOX] === RESUMO DE FILTROS ===", True)
    log_msg(f"  Raw: {len(all_raw)} | type!=income: {filter_counts['type_not_income']} | status!=paid: {filter_counts['status_not_paid']} | debit!=ASAAS: {filter_counts['debit_bank_not_asaas']} | date!=target: {filter_counts['date_mismatch']} | MANTIDAS: {filter_counts['kept']}", True)
    log_msg(f"[ADVBOX] TOTAL: {len(transactions)} transações", True)

    return transactions


# ---------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ---------------------------------------------------------------------------
if not ASAAS_TOKEN or not ADVBOX_TOKEN:
    log_msg(f"\n❌ ERRO CRÍTICO: Tokens não fornecidos!", True)
    if ASAAS_TOKEN:
        log_msg(f"  ✓ ASAAS_TOKEN: definido ({len(ASAAS_TOKEN)} chars)", True)
    else:
        log_msg(f"  ✗ ASAAS_TOKEN: VAZIO ou NÃO DEFINIDO", True)
    if ADVBOX_TOKEN:
        log_msg(f"  ✓ ADVBOX_TOKEN: definido ({len(ADVBOX_TOKEN)} chars)", True)
    else:
        log_msg(f"  ✗ ADVBOX_TOKEN: VAZIO ou NÃO DEFINIDO", True)
    sys.exit(1)

log_msg(f"\n🔄 INICIANDO LOOP DE RECONCILIAÇÃO", True)

headers_advbox = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

attempt = 0
reconciliation_complete = False
all_corrections = []
total_asaas_final = 0
total_advbox_final = 0

while attempt < MAX_RECONCILIATION_ATTEMPTS and not reconciliation_complete:
    attempt += 1
    log_msg(f"\n{'='*100}\nTENTATIVA {attempt}/{MAX_RECONCILIATION_ATTEMPTS}\n{'='*100}", True)

    log_msg(f"\n[LEITURA 1] Buscando transações...", True)
    asaas_transactions = fetch_asaas_transactions()
    advbox_transactions = fetch_advbox_transactions()

    total_asaas = sum(float(tx.get("value", 0)) for tx in asaas_transactions)
    total_advbox = sum(
        float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
        for tx in advbox_transactions
    )

    log_msg(f"\nAsaas:  {len(asaas_transactions)} tx | R$ {total_asaas:.2f}", True)
    log_msg(f"Advbox: {len(advbox_transactions)} tx | R$ {total_advbox:.2f}", True)

    log_msg(f"\n[MATCHING] Identificando divergências...", True)

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

    log_msg(f"Matches: {len(matched)} | Faltando: {len(unmatched_asaas)} | Fantasmas: {len(unmatched_advbox)}", True)

    # Correções
    if unmatched_advbox and not DRY_RUN:
        log_msg(f"\n[CORRIGINDO] Removendo {len(unmatched_advbox)} fantasma(s)...", True)
        for tx in unmatched_advbox:
            tx_id = tx.get("id", "")
            valor = float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
            if tx_id:
                if delete_advbox_transaction(tx_id, headers_advbox):
                    all_corrections.append(("DELETE", valor))

    if unmatched_asaas and not DRY_RUN:
        log_msg(f"\n[CORRIGINDO] Criando {len(unmatched_asaas)} faltante(s)...", True)
        for tx in unmatched_asaas:
            valor = float(tx.get("value", 0))
            if create_advbox_transaction(tx, headers_advbox):
                all_corrections.append(("CREATE", valor))

    # Dupla checagem
    log_msg(f"\n[DUPLA CHECAGEM] Relendo...", True)
    asaas_transactions_check = fetch_asaas_transactions()
    advbox_transactions_check = fetch_advbox_transactions()

    total_asaas_final = sum(float(tx.get("value", 0)) for tx in asaas_transactions_check)
    total_advbox_final = sum(
        float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
        for tx in advbox_transactions_check
    )

    diferenca = abs(total_asaas_final - total_advbox_final)

    log_msg(f"\nAsaas (dupla):  R$ {total_asaas_final:.2f}", True)
    log_msg(f"Advbox (dupla): R$ {total_advbox_final:.2f}", True)
    log_msg(f"Diferença: R$ {diferenca:.2f}", True)

    if diferenca < TOLERANCE:
        log_msg(f"\n✅ VALORES BATEM!", True)
        reconciliation_complete = True
    else:
        if attempt < MAX_RECONCILIATION_ATTEMPTS:
            log_msg(f"⚠️  Tentando novamente...", True)
        else:
            log_msg(f"❌ Limite de tentativas atingido", True)

# RELATÓRIO FINAL
log_msg(f"\n{'='*100}\nRESULTADO FINAL\n{'='*100}", True)

if reconciliation_complete:
    log_msg(f"✅ CONCILIAÇÃO OK em {attempt} tentativa(s)", True)
else:
    log_msg(f"❌ NÃO CONCILIADA após {attempt} tentativa(s)", True)

log_msg(f"  Asaas: R$ {total_asaas_final:.2f}", True)
log_msg(f"  Advbox: R$ {total_advbox_final:.2f}", True)
log_msg(f"  Diferença: R$ {abs(total_asaas_final - total_advbox_final):.2f}", True)
log_msg(f"  Correções: {len(all_corrections)}", True)

# Relatório JSON
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
            {"tipo": corr[0], "valor": round(corr[1], 2)}
            for corr in all_corrections
        ],
    },
}

nome_relatorio = f"relatorio_{TARGET_DATE}.json"
with open(nome_relatorio, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

log_msg(f"\n📄 Relatório: {nome_relatorio}", True)
log_msg(f"📋 Log detalhado: {LOG_FILE}", True)
log_msg(f"\n{'='*100}\nFIM DO LOG\n{'='*100}", True)
