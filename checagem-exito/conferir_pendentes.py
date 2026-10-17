"""Conferência SOMENTE LEITURA: lançamentos da CONTADORIA sem data de pagamento (vencidos)
cruzados com os recebimentos do Asaas pelo número do processo.

Não grava nada no Advbox. Não imprime nomes de clientes nem números completos de processo.
"""

import os
import sys
from collections import defaultdict
from datetime import date, datetime

import os
import re
import time
from datetime import timedelta

import requests

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ASAAS_BASE = "https://api.asaas.com/v3"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "").strip()
CONTA = "CONTADORIA"
TIPOS_RECEITA = {"PAYMENT_RECEIVED", "RECEIVABLE_ANTICIPATION_GROSS_CREDIT"}


class _C:
    ADVBOX_TOKEN = ADVBOX_TOKEN
    ASAAS_TOKEN = ASAAS_TOKEN
    ASAAS_BASE = ASAAS_BASE
    TIPOS_RECEITA = TIPOS_RECEITA
    time = time

    @staticmethod
    def extrair_digitos(texto: str) -> str:
        return re.sub(r"\D", "", texto or "")


c = _C

HOJE = date.today().isoformat()
INICIO_ASAAS = os.environ.get("INICIO_ASAAS", "2025-01-01")


def mascarar(processo: str) -> str:
    d = c.extrair_digitos(processo)
    return f"****{d[-6:]}" if len(d) >= 6 else "(sem número)"


def advbox_contadoria_sem_pagamento() -> list[dict]:
    """Receitas da conta CONTADORIA, todas as páginas (somente GET)."""
    headers = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    todos, offset = [], 0
    while True:
        resp = requests.get(f"{ADVBOX_BASE}/transactions", headers=headers,
                            params={"entry_type": "income", "limit": 1000, "offset": offset}, timeout=60)
        resp.raise_for_status()
        pag = resp.json()
        dados = pag.get("data") or []
        todos.extend(dados)
        offset += len(dados)
        if not dados or offset >= int(pag.get("totalCount", offset)):
            break
    return [t for t in todos
            if (t.get("debit_bank") or "").upper() == CONTA
            and t.get("entry_type") == "income" and not t.get("date_payment")]


def janelas_mensais(inicio: str, fim: str):
    atual = datetime.fromisoformat(inicio).date().replace(day=1)
    limite = datetime.fromisoformat(fim).date()
    while atual <= limite:
        proximo = (atual.replace(day=28) + timedelta(days=4)).replace(day=1)
        fim_mes = min(proximo - timedelta(days=1), limite)
        yield atual.isoformat(), fim_mes.isoformat()
        atual = proximo


def recebimentos_asaas() -> list[dict]:
    todos = []
    for ini, fim in janelas_mensais(INICIO_ASAAS, HOJE):
        offset = 0
        while True:
            resp = requests.get(
                f"{c.ASAAS_BASE}/financialTransactions",
                headers={"access_token": c.ASAAS_TOKEN},
                params={"startDate": ini, "finishDate": fim, "limit": 100, "offset": offset},
                timeout=30,
            )
            resp.raise_for_status()
            pag = resp.json()
            itens = pag.get("data", [])
            todos.extend(i for i in itens if i.get("type") in c.TIPOS_RECEITA)
            if not pag.get("hasMore") or not itens:
                break
            offset += 100
            c.time.sleep(0.3)
    return todos


def main() -> int:
    if not c.ADVBOX_TOKEN or not c.ASAAS_TOKEN:
        print("ERRO: ADVBOX_TOKEN e/ou ASAAS_TOKEN não configurados.")
        return 1

    lancs = advbox_contadoria_sem_pagamento()
    vencidos = [l for l in lancs if (l.get("date_due") or "9999")[:10] < HOJE]
    print(f"Advbox CONTADORIA: {len(lancs)} sem data de pagamento, {len(vencidos)} já vencidos.")

    recebs = recebimentos_asaas()
    print(f"Asaas (desde {INICIO_ASAAS}): {len(recebs)} recebimentos.")

    por_digitos = defaultdict(list)
    for r in recebs:
        ref = c.extrair_digitos(r.get("externalReference") or "")
        if len(ref) >= 15:
            por_digitos[ref].append(r)

    com_proc = sem_proc = achados = 0
    sem_receb = []
    for l in vencidos:
        proc = c.extrair_digitos(l.get("process_number") or "")
        if len(proc) < 15:
            sem_proc += 1
            continue
        com_proc += 1
        casados = [r for ref, rs in por_digitos.items()
                   if proc in ref or ref.endswith(proc) for r in rs]
        if casados:
            achados += 1
            print(f"  ACHADO {mascarar(proc)} venc {l.get('date_due','')[:10]} "
                  f"Advbox {l.get('amount')} | Asaas {[(x.get('date'), x.get('value')) for x in casados][:3]}")
        else:
            sem_receb.append(mascarar(proc) + f" venc {(l.get('date_due') or '')[:10]} valor {l.get('amount')}")

    print(f"\nResumo vencidos: {len(vencidos)} | sem número de processo: {sem_proc} | "
          f"com processo: {com_proc} | recebimento encontrado no Asaas: {achados} | "
          f"sem recebimento no Asaas: {len(sem_receb)}")
    for linha in sem_receb[:60]:
        print("  SEM RECEBIMENTO", linha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
