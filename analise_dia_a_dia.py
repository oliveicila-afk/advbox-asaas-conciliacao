#!/usr/bin/env python3
"""
Conciliação Diária — Asaas vs Advbox
Busca TODAS as receitas recebidas em uma data, compara e CORRIGE divergências.

REGRA OBRIGATÓRIA:
  Quando Asaas mostra um total X em um dia, Advbox DEVE ter EXATAMENTE X
  dos MESMOS clientes, MESMOS pagamentos, data CORRETA. Se não, corrige.

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
# PAYMENT_RECEIVED  = cobrança paga pelo cliente (boleto, Pix, cartão)
# ANTICIPATED_RECEIVED = antecipação de recebível (Asaas adianta o valor antes do vencimento)
ASAAS_INCOME_TYPES = ["PAYMENT_RECEIVED", "ANTICIPATED_RECEIVED"]

# Modo DRY-RUN: se True, mostra o que FARIA, sem executar as correções
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ["true", "1", "yes"]

# IDs de categorias para análise CAMADA 2 (categoria)
CATEGORIAS_HONORARIOS_INICIAIS = [51, 52, 53]  # ajuste conforme sua Advbox
CATEGORIAS_HONORARIOS_EXITO = [54, 55, 56]     # ajuste conforme sua Advbox
CATEGORIAS_HONORARIOS_INCUMBENCIAL = [57, 58]  # ajuste conforme sua Advbox

# Cost centers para análise CAMADA 4 (origin)
COST_CENTER_ASAAS_PADRAO = 60814

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
            print(f"  ❌ Erro ao deletar {tx_id}: {resp.status_code} — {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Erro ao deletar {tx_id}: {e}")
        return False


def create_advbox_transaction(asaas_tx: dict, headers_advbox: dict) -> bool:
    """Cria uma transação no Advbox baseada em uma transação do Asaas."""
    try:
        # Análise CAMADA 2 (categoria) e CAMADA 4 (cost center)
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
            "external_id": asaas_tx.get("id", ""),  # rastrear origem Asaas
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
            print(f"  ❌ Erro ao criar: {resp.status_code} — {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Erro ao criar: {e}")
        return False


def inferir_categoria(description: str) -> int:
    """
    CAMADA 2: Infere a categoria de honorário baseado na descrição.
    Retorna o ID da categoria apropriada.
    """
    desc_lower = description.lower()

    # Análise de keywords para classificação
    if any(kw in desc_lower for kw in ["êxito", "sucesso", "êxito", "honorário de êxito"]):
        return CATEGORIAS_HONORARIOS_EXITO[0]
    elif any(kw in desc_lower for kw in ["inicial", "protocolo", "entrada", "primeira"]):
        return CATEGORIAS_HONORARIOS_INICIAIS[0]
    elif any(kw in desc_lower for kw in ["incumbencial", "mensal", "recursal"]):
        return CATEGORIAS_HONORARIOS_INCUMBENCIAL[0]

    # Padrão: honorários iniciais
    return CATEGORIAS_HONORARIOS_INICIAIS[0]


def analisar_origin(tx: dict) -> str:
    """
    CAMADA 4: Infere a origem/cost center baseado nos dados da transação.
    """
    debit_bank = tx.get("debit_bank", "")
    if debit_bank == "ASAAS":
        return "ASAAS"
    return "MANUAL"


print("=" * 100)
print(f"CONCILIAÇÃO DIÁRIA — {TARGET_DATE}")
if DRY_RUN:
    print("(MODO DRY-RUN — sem executar correções)")
else:
    print("(MODO CORRETIVO — executando correções)")
print("=" * 100)

# Verificar se os tokens necessários foram fornecidos
if not ASAAS_TOKEN or not ADVBOX_TOKEN:
    print("\n❌ ERRO CRÍTICO: Tokens não fornecidos!")
    print(f"  ASAAS_TOKEN: {'✓ Definido' if ASAAS_TOKEN else '✗ FALTANDO'}")
    print(f"  ADVBOX_TOKEN: {'✓ Definido' if ADVBOX_TOKEN else '✗ FALTANDO'}")
    print("\nVerifique se os secrets do repositório GitHub estão configurados corretamente.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 1. ASAAS — buscar TODAS as receitas do dia
# ---------------------------------------------------------------------------
print(f"\n[1/3] Asaas — buscando receitas de {TARGET_DATE} ...")
print("-" * 100)

asaas_transactions = []

headers_asaas = {
    "Authorization": f"Bearer {ASAAS_TOKEN}",
    "Accept": "application/json"
}

for income_type in ASAAS_INCOME_TYPES:
    offset = 0
    limit  = 100

    while True:
        try:
            resp = requests.get(
                "https://api.asaas.com/v3/financialTransactions",
                headers=headers_asaas,
                params={
                    "startDate": TARGET_DATE,   # data de crédito na conta
                    "finishDate": TARGET_DATE,
                    "type": income_type,
                    "limit": limit,
                    "offset": offset,
                },
                timeout=30
            )

            if resp.status_code != 200:
                print(f"❌ Asaas ({income_type}): status {resp.status_code} — {resp.text[:300]}")
                break

            data = resp.json()
            batch = data.get("data", [])
            asaas_transactions.extend(batch)

            # Paginação: continua enquanto houver mais páginas
            has_more = data.get("hasMore", False)
            if not has_more or len(batch) == 0:
                break
            offset += limit

        except Exception as e:
            print(f"❌ Erro ao conectar Asaas ({income_type}): {e}")
            break

if asaas_transactions:
    print(f"✓ {len(asaas_transactions)} lançamentos encontrados\n")
    print(f"{'#':<4} {'Tipo':<25} {'Descrição':<45} {'Valor':>12}")
    print("-" * 100)
    for i, tx in enumerate(asaas_transactions, 1):
        tipo  = tx.get("type", "N/A")
        desc  = tx.get("description", "N/A")[:45]
        valor = float(tx.get("value", 0))
        data  = tx.get("dateTime", "N/A")[:10] if tx.get("dateTime") else "N/A"
        print(f"{i:<4} {tipo:<25} {desc:<45} R$ {valor:>10.2f} ({data})")
else:
    print(f"⚠️  Nenhuma receita encontrada para {TARGET_DATE}")

# DEBUG: Mostrar estrutura completa da primeira transação Asaas
if asaas_transactions:
    print(f"\n[DEBUG ASAAS] Estrutura da primeira transação:")
    print(f"  {asaas_transactions[0]}\n")

total_asaas = sum(float(tx.get("value", 0)) for tx in asaas_transactions)
print(f"\n{'':>80} TOTAL ASAAS: R$ {total_asaas:>10.2f}")

# ---------------------------------------------------------------------------
# 2. ADVBOX — buscar todas as receitas RECEBIDAS (pagas) no dia
# ---------------------------------------------------------------------------
print(f"\n[2/3] Advbox — buscando receitas de {TARGET_DATE} ...")
print("-" * 100)

advbox_transactions = []

headers_advbox = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "Accept": "application/json"
}

offset = 0
limit = 100

while True:
    try:
        # IMPORTANTE: Advbox API não suporta filtros por data/status na query
        # Buscamos TUDO e filtramos em Python
        resp = requests.get(
            "https://app.advbox.com.br/api/v1/transactions",
            headers=headers_advbox,
            params={
                "limit": limit,
                "offset": offset,
            },
            timeout=30
        )

        if resp.status_code != 200:
            print(f"❌ Advbox: status {resp.status_code} — {resp.text[:300]}")
            break

        data = resp.json()
        batch = data.get("data", []) or data.get("transactions", [])

        # DEBUG: Log de transações brutas recebidas (apenas no primeiro batch)
        if offset == 0 and batch:
            print(f"\n[DEBUG ADVBOX] Primeiras 2 transações brutas da API:")
            for i, tx in enumerate(batch[:2]):
                print(f"  Tx {i+1}: {tx}\n")

        # Filtragem em Python: apenas receitas da Asaas que foram pagas no dia
        batch_antes = len(batch)
        for tx in batch:
            # Filtro 1: Apenas receitas (income)
            tipo = tx.get("type")
            if tipo != "income":
                if offset == 0:  # Log apenas no primeiro batch
                    print(f"[FILTER 1] Tx removida: type={tipo} (esperado 'income')")
                continue

            # Filtro 2: Apenas lançamentos efetivamente recebidos (status paid)
            status = tx.get("status")
            if status != "paid":
                if offset == 0:
                    print(f"[FILTER 2] Tx removida: status={status} (esperado 'paid')")
                continue

            # Filtro 3: Apenas da conta Asaas (debit_bank == "ASAAS")
            debit_bank = tx.get("debit_bank")
            if debit_bank != "ASAAS":
                if offset == 0:
                    print(f"[FILTER 3] Tx removida: debit_bank={debit_bank} (esperado 'ASAAS')")
                continue

            # Filtro 4: Data de pagamento = TARGET_DATE
            payment_date = tx.get("payment_date", tx.get("date", ""))
            if payment_date and payment_date[:10] != TARGET_DATE:
                if offset == 0:
                    print(f"[FILTER 4] Tx removida: payment_date={payment_date[:10]} (esperado {TARGET_DATE})")
                continue

            advbox_transactions.append(tx)

        # DEBUG: Contagem de filtros
        if offset == 0:
            print(f"\n[DEBUG ADVBOX] Batch 1: {batch_antes} transações → {len(advbox_transactions)} após filtros\n")

        # Paginação: continua se houver mais dados
        if len(batch) < limit:
            break
        offset += limit

    except Exception as e:
        print(f"❌ Erro ao conectar Advbox: {e}")
        break

if advbox_transactions:
    print(f"✓ {len(advbox_transactions)} lançamentos encontrados\n")
    print(f"{'#':<4} {'Descrição':<50} {'Valor':>12}")
    print("-" * 100)
    for i, tx in enumerate(advbox_transactions, 1):
        desc  = tx.get("description", tx.get("name", "N/A"))[:50]
        valor = float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
        print(f"{i:<4} {desc:<50} R$ {valor:>10.2f}")

    # DEBUG: Mostrar estrutura da primeira transação Advbox que passou nos filtros
    print(f"\n[DEBUG ADVBOX] Estrutura da primeira transação filtrada:")
    print(f"  {advbox_transactions[0]}\n")
else:
    print(f"⚠️  Nenhuma receita encontrada para {TARGET_DATE}")
    print(f"\n[DEBUG ADVBOX] Nenhuma transação passou nos filtros!")
    print(f"  Verifique os campos esperados na API do Advbox:")
    print(f"  - type (esperado: 'income')")
    print(f"  - status (esperado: 'paid')")
    print(f"  - debit_bank (esperado: 'ASAAS')")
    print(f"  - payment_date ou date (esperado: {TARGET_DATE})\n")

total_advbox = sum(
    float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
    for tx in advbox_transactions
)
print(f"\n{'':>80} TOTAL ADVBOX: R$ {total_advbox:>10.2f}")

# ---------------------------------------------------------------------------
# 3. COMPARAÇÃO E MATCHING
# ---------------------------------------------------------------------------
print(f"\n[3/3] Comparação e Matching ...")
print("=" * 100)

# Indexar por valor para matching
def index_by_value(txs, value_key_fn):
    idx = {}
    for tx in txs:
        v = round(value_key_fn(tx), 2)
        idx.setdefault(v, []).append(tx)
    return idx

asaas_idx  = index_by_value(asaas_transactions, lambda tx: float(tx.get("value", 0)))
advbox_idx = index_by_value(
    advbox_transactions,
    lambda tx: float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
)

print(f"\n[DEBUG MATCHING] Índices criados:")
print(f"  Asaas:  {len(asaas_idx)} valores únicos")
print(f"  Advbox: {len(advbox_idx)} valores únicos")
print(f"\n[DEBUG MATCHING] Valores Asaas: {sorted(asaas_idx.keys())}")
print(f"[DEBUG MATCHING] Valores Advbox: {sorted(advbox_idx.keys())}")

matched         = []
unmatched_asaas = []
remaining_advbox = {v: list(txs) for v, txs in advbox_idx.items()}

for valor, asaas_list in asaas_idx.items():
    for asaas_tx in asaas_list:
        if valor in remaining_advbox and remaining_advbox[valor]:
            advbox_tx = remaining_advbox[valor].pop(0)
            matched.append((asaas_tx, advbox_tx, valor))
            print(f"[MATCH] R$ {valor:.2f} | {asaas_tx.get('description', '')[:40]} = {advbox_tx.get('description', advbox_tx.get('name', ''))[:40]}")
        else:
            unmatched_asaas.append(asaas_tx)
            print(f"[UNMATCHED ASAAS] R$ {valor:.2f} não encontrado no Advbox")

unmatched_advbox = [tx for txs in remaining_advbox.values() for tx in txs]
for tx in unmatched_advbox:
    valor = float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
    print(f"[PHANTOM ADVBOX] R$ {valor:.2f} | {tx.get('description', tx.get('name', ''))[:40]}")

# ---------------------------------------------------------------------------
# 4. EXECUÇÃO DE CORREÇÕES
# ---------------------------------------------------------------------------
print(f"\n[4/4] Executando Correções ...")
print("=" * 100)

corrections_made = []
corrections_failed = []

# A. REMOVER transações que estão SÓ no Advbox (fantasmas)
if unmatched_advbox:
    print(f"\n🗑️  REMOVENDO {len(unmatched_advbox)} transação(ões) fantasma(s) do Advbox:")
    for tx in unmatched_advbox:
        valor = float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
        desc  = tx.get("description", tx.get("name", "N/A"))
        tx_id = tx.get("id", "")

        print(f"\n  • R$ {valor:.2f} | {desc[:60]}")

        if not DRY_RUN and tx_id:
            if delete_advbox_transaction(tx_id, headers_advbox):
                print(f"    ✓ Removida com sucesso")
                corrections_made.append(("DELETE", valor, desc))
            else:
                corrections_failed.append(("DELETE", valor, desc))
        elif DRY_RUN:
            print(f"    (DRY-RUN: seria removida)")
            corrections_made.append(("DELETE", valor, desc))

# B. CRIAR transações que estão SÓ no Asaas (faltando)
if unmatched_asaas:
    print(f"\n✨ CRIANDO {len(unmatched_asaas)} transação(ões) faltante(s) no Advbox:")
    for tx in unmatched_asaas:
        valor = float(tx.get("value", 0))
        desc  = tx.get("description", "N/A")

        print(f"\n  • R$ {valor:.2f} | {desc[:60]}")

        if not DRY_RUN:
            if create_advbox_transaction(tx, headers_advbox):
                print(f"    ✓ Criada com sucesso")
                corrections_made.append(("CREATE", valor, desc))
            else:
                corrections_failed.append(("CREATE", valor, desc))
        else:
            print(f"    (DRY-RUN: seria criada)")
            corrections_made.append(("CREATE", valor, desc))

print(f"\n✅ ENCONTRADOS EM AMBOS ({len(matched)}):\n")
for asaas_tx, advbox_tx, valor in matched:
    print(f"  R$ {valor:.2f}")
    print(f"    Asaas:  {asaas_tx.get('description', '')[:60]}")
    print(f"    Advbox: {advbox_tx.get('description', advbox_tx.get('name', ''))[:60]}\n")

print(f"\n⚠️  SÓ NO ASAAS — não encontrados no Advbox ({len(unmatched_asaas)}):\n")
for tx in unmatched_asaas:
    print(f"  R$ {float(tx.get('value', 0)):.2f} | {tx.get('description', 'N/A')[:70]}")

print(f"\n⚠️  SÓ NO ADVBOX — não encontrados no Asaas ({len(unmatched_advbox)}):\n")
for tx in unmatched_advbox:
    valor = float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
    desc  = tx.get("description", tx.get("name", "N/A"))
    print(f"  R$ {valor:.2f} | {desc[:70]}")

# ---------------------------------------------------------------------------
# 5. RESUMO FINAL REVISADO
# ---------------------------------------------------------------------------
print("\n" + "=" * 100)
print(f"RESUMO FINAL — {TARGET_DATE}")
print("=" * 100)

# Totais DEPOIS das correções
total_asaas_final = total_asaas
total_advbox_final = total_advbox - sum(
    float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
    for tx in unmatched_advbox
) + sum(
    float(tx.get("value", 0))
    for tx in unmatched_asaas
)

diferenca_final = total_asaas_final - total_advbox_final
status    = "✅ CONCILIADO" if abs(diferenca_final) < 0.10 else f"⚠️  DIVERGÊNCIA: R$ {abs(diferenca_final):.2f}"

print(f"""
  ANTES DAS CORREÇÕES:
  Asaas  : {len(asaas_transactions):>3} lançamentos | Total: R$ {total_asaas:>10.2f}
  Advbox : {len(advbox_transactions):>3} lançamentos | Total: R$ {total_advbox:>10.2f}
  -------
  Matches: {len(matched):>3}
  Faltando: {len(unmatched_asaas):>3} | R$ {sum(float(t.get('value',0)) for t in unmatched_asaas):.2f}
  Fantasmas: {len(unmatched_advbox):>3} | R$ {sum(float(str(t.get('value',t.get('amount',0))).replace(',','.')) for t in unmatched_advbox):.2f}

  DEPOIS DAS CORREÇÕES:
  Asaas  : {len(asaas_transactions):>3} lançamentos | Total: R$ {total_asaas_final:>10.2f}
  Advbox : {len(advbox_transactions) - len(unmatched_advbox) + len(unmatched_asaas):>3} lançamentos | Total: R$ {total_advbox_final:>10.2f}

  CORREÇÕES REALIZADAS: {len(corrections_made)}
  CORREÇÕES FALHADAS: {len(corrections_failed)}

  {status}
""")

# ---------------------------------------------------------------------------
# 5. SALVAR RELATÓRIO JSON
# ---------------------------------------------------------------------------
report = {
    "data": TARGET_DATE,
    "gerado_em": datetime.now().isoformat(),
    "asaas": {
        "total_lancamentos": len(asaas_transactions),
        "total_valor": round(total_asaas, 2),
        "tipos_buscados": ASAAS_INCOME_TYPES,
        "lancamentos": [
            {
                "tipo": tx.get("type"),
                "descricao": tx.get("description", ""),
                "valor": float(tx.get("value", 0)),
                "data": tx.get("dateTime", "")[:10] if tx.get("dateTime") else "",
            }
            for tx in asaas_transactions
        ],
    },
    "advbox": {
        "total_lancamentos": len(advbox_transactions),
        "total_valor": round(total_advbox, 2),
        "lancamentos": [
            {
                "descricao": tx.get("description", tx.get("name", "")),
                "valor": float(str(tx.get("value", tx.get("amount", 0))).replace(",", ".")),
                "data_pagamento": tx.get("payment_date", tx.get("date", "")),
            }
            for tx in advbox_transactions
        ],
    },
    "conciliacao": {
        "matches": len(matched),
        "faltando_no_advbox": len(unmatched_asaas),
        "fantasmas_no_advbox": len(unmatched_advbox),
        "diferenca_antes": round(total_asaas - total_advbox, 2),
        "diferenca_depois": round(diferenca_final, 2),
        "status": status,
    },
    "correcoes": {
        "total_realizadas": len(corrections_made),
        "total_falhadas": len(corrections_failed),
        "detalhes": [
            {
                "tipo": corr[0],
                "valor": round(corr[1], 2),
                "descricao": corr[2]
            }
            for corr in corrections_made
        ],
        "falhas": [
            {
                "tipo": corr[0],
                "valor": round(corr[1], 2),
                "descricao": corr[2]
            }
            for corr in corrections_failed
        ],
    },
}

nome_arquivo = f"relatorio_{TARGET_DATE}.json"
with open(nome_arquivo, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"  📄 Relatório salvo: {nome_arquivo}\n")
