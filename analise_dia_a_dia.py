#!/usr/bin/env python3
"""
Conciliação Diária — Asaas vs Advbox
Busca TODAS as receitas recebidas em uma data e compara os dois sistemas.

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

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "").strip()
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
TARGET_DATE  = os.environ.get("TARGET_DATE", "2026-09-01").strip()

# Tipos de lançamento do Asaas que representam RECEITA recebida
# PAYMENT_RECEIVED  = cobrança paga pelo cliente (boleto, Pix, cartão)
# ANTICIPATED_RECEIVED = antecipação de recebível (Asaas adianta o valor antes do vencimento)
ASAAS_INCOME_TYPES = ["PAYMENT_RECEIVED", "ANTICIPATED_RECEIVED"]

print("=" * 100)
print(f"CONCILIAÇÃO DIÁRIA — {TARGET_DATE}")
print("=" * 100)

# ---------------------------------------------------------------------------
# 1. ASAAS — buscar TODAS as receitas do dia
# ---------------------------------------------------------------------------
print(f"\n[1/3] Asaas — buscando receitas de {TARGET_DATE} ...")
print("-" * 100)

asaas_transactions = []

if not ASAAS_TOKEN:
    print("❌ ASAAS_TOKEN não definido — verifique os secrets do repositório")
else:
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
            print(f"{i:<4} {tipo:<25} {desc:<45} R$ {valor:>10.2f}")
    else:
        print(f"⚠️  Nenhuma receita encontrada para {TARGET_DATE}")

total_asaas = sum(float(tx.get("value", 0)) for tx in asaas_transactions)
print(f"\n{'':>80} TOTAL ASAAS: R$ {total_asaas:>10.2f}")

# ---------------------------------------------------------------------------
# 2. ADVBOX — buscar todas as receitas RECEBIDAS (pagas) no dia
# ---------------------------------------------------------------------------
print(f"\n[2/3] Advbox — buscando receitas de {TARGET_DATE} ...")
print("-" * 100)

advbox_transactions = []

if not ADVBOX_TOKEN:
    print("❌ ADVBOX_TOKEN não definido — verifique os secrets do repositório")
else:
    headers_advbox = {
        "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "Accept": "application/json"
    }

    page = 1

    while True:
        try:
            resp = requests.get(
                "https://app.advbox.com.br/api/v1/transactions",
                headers=headers_advbox,
                params={
                    "type": "income",            # apenas receitas
                    "payment_date_from": TARGET_DATE,  # filtra por DATA DE PAGAMENTO
                    "payment_date_to":   TARGET_DATE,  # (não data de vencimento)
                    "status": "paid",            # apenas lançamentos efetivamente recebidos
                    "per_page": 100,
                    "page": page,
                },
                timeout=30
            )

            if resp.status_code != 200:
                print(f"❌ Advbox: status {resp.status_code} — {resp.text[:300]}")
                break

            data = resp.json()
            batch = data.get("data", []) or data.get("transactions", [])
            advbox_transactions.extend(batch)

            # Paginação
            total_pages = data.get("last_page", data.get("meta", {}).get("last_page", 1))
            if page >= total_pages or len(batch) == 0:
                break
            page += 1

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
    else:
        print(f"⚠️  Nenhuma receita encontrada para {TARGET_DATE}")

total_advbox = sum(
    float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
    for tx in advbox_transactions
)
print(f"\n{'':>80} TOTAL ADVBOX: R$ {total_advbox:>10.2f}")

# ---------------------------------------------------------------------------
# 3. COMPARAÇÃO
# ---------------------------------------------------------------------------
print(f"\n[3/3] Comparação ...")
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

matched         = []
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
# 4. RESUMO FINAL
# ---------------------------------------------------------------------------
print("\n" + "=" * 100)
print(f"RESUMO FINAL — {TARGET_DATE}")
print("=" * 100)
diferenca = total_asaas - total_advbox
status    = "✅ CONCILIADO" if abs(diferenca) < 0.10 else f"⚠️  DIFERENÇA DE R$ {abs(diferenca):.2f}"

print(f"""
  Asaas  : {len(asaas_transactions):>3} lançamentos | Total: R$ {total_asaas:>10.2f}
  Advbox : {len(advbox_transactions):>3} lançamentos | Total: R$ {total_advbox:>10.2f}
  -------
  Matches: {len(matched):>3}
  Só Asaas : {len(unmatched_asaas):>3} | R$ {sum(float(t.get('value',0)) for t in unmatched_asaas):.2f}
  Só Advbox: {len(unmatched_advbox):>3} | R$ {sum(float(str(t.get('value',t.get('amount',0))).replace(',','.')) for t in unmatched_advbox):.2f}

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
        "so_asaas": len(unmatched_asaas),
        "so_advbox": len(unmatched_advbox),
        "diferenca": round(diferenca, 2),
        "status": status,
    },
}

nome_arquivo = f"relatorio_{TARGET_DATE}.json"
with open(nome_arquivo, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"  📄 Relatório salvo: {nome_arquivo}\n")
