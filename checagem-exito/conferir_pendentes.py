"""Conferência SOMENTE LEITURA.

1) Lançamentos de receita da conta CONTADORIA (Advbox) vencidos e sem data de pagamento,
   cruzados com os recebimentos do Asaas pelo número do processo.
2) Para cada um desses processos, lê o histórico e as tarefas no Advbox e procura
   palavras que indiquem recebimento/valor que caiu.

Não grava nada em lugar nenhum. Não imprime nomes de clientes, textos de tarefas
nem números completos de processo (só os 6 últimos dígitos).
"""

import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import requests

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ASAAS_BASE = "https://api.asaas.com/v3"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "").strip()
CONTA = "CONTADORIA"
TIPOS_RECEITA = {"PAYMENT_RECEIVED", "RECEIVABLE_ANTICIPATION_GROSS_CREDIT"}
HOJE = date.today().isoformat()
INICIO_ASAAS = os.environ.get("INICIO_ASAAS", "2025-01-01")

# Palavras que indicam recebimento / valor que caiu (só as palavras são impressas)
PALAVRAS = re.compile(
    r"caiu|caiu na conta|recebid|pagament|pago|quitad|baixa|depositad|transferid|"
    r"\bTED\b|\bPIX\b|honor[áa]ri|alvar[áa]|êxito|exito|liquidad",
    re.IGNORECASE,
)


def digitos(texto) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def mascarar(processo) -> str:
    d = digitos(processo)
    return f"****{d[-6:]}" if len(d) >= 6 else "(sem número)"


def _get(url, headers, params=None, tentativas=4):
    """GET com espera em caso de 429 (limite ~30/min no Advbox)."""
    for i in range(tentativas):
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", "5")) + 1)
            continue
        return resp
    return resp


def _advbox_headers():
    return {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"}


def advbox_contadoria_sem_pagamento() -> list[dict]:
    """Receitas da conta CONTADORIA sem data de pagamento (somente GET)."""
    todos, offset = [], 0
    while True:
        resp = _get(f"{ADVBOX_BASE}/transactions", _advbox_headers(),
                    {"entry_type": "income", "limit": 1000, "offset": offset})
        resp.raise_for_status()
        pag = resp.json()
        dados = pag.get("data") or []
        todos.extend(dados)
        offset += len(dados)
        if not dados or offset >= int(pag.get("totalCount", offset)):
            break
    return [t for t in todos
            if (t.get("debit_bank") or "").upper() == CONTA
            and not t.get("date_payment")]


def janelas_mensais(inicio: str, fim: str):
    atual = datetime.fromisoformat(inicio).date().replace(day=1)
    limite = datetime.fromisoformat(fim).date()
    while atual <= limite:
        proximo = (atual.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield atual.isoformat(), min(proximo - timedelta(days=1), limite).isoformat()
        atual = proximo


def recebimentos_asaas() -> list[dict]:
    todos = []
    for ini, fim in janelas_mensais(INICIO_ASAAS, HOJE):
        offset = 0
        while True:
            resp = requests.get(
                f"{ASAAS_BASE}/financialTransactions",
                headers={"access_token": ASAAS_TOKEN},
                params={"startDate": ini, "finishDate": fim, "limit": 100, "offset": offset},
                timeout=30,
            )
            resp.raise_for_status()
            pag = resp.json()
            itens = pag.get("data", [])
            todos.extend(i for i in itens if i.get("type") in TIPOS_RECEITA)
            if not pag.get("hasMore") or not itens:
                break
            offset += 100
            time.sleep(0.3)
    return todos


def id_processo(lanc: dict):
    """O id do processo pode vir como lawsuit_id ou lawsuits_id, conforme o endpoint."""
    return lanc.get("lawsuit_id") or lanc.get("lawsuits_id")


def ler_tarefas(lawsuit_id) -> list[dict]:
    """Histórico e tarefas (posts) do processo. Retorna lista de itens (somente leitura)."""
    itens = []
    for caminho, params in ((f"/history/{lawsuit_id}", None),
                            ("/posts", {"lawsuits_id": lawsuit_id, "limit": 100})):
        resp = _get(f"{ADVBOX_BASE}{caminho}", _advbox_headers(), params)
        if resp.status_code != 200:
            print(f"    {caminho.split('/')[1]}: HTTP {resp.status_code}")
            continue
        corpo = resp.json()
        lista = corpo.get("data", corpo) if isinstance(corpo, dict) else corpo
        if isinstance(lista, list):
            itens.extend(x for x in lista if isinstance(x, dict))
        time.sleep(2.2)
    return itens


def texto_do_item(item: dict) -> str:
    partes = []
    for campo in ("task", "notes", "comments", "description", "title", "content", "text"):
        v = item.get(campo)
        if isinstance(v, str):
            partes.append(v)
    return " ".join(partes)


def data_do_item(item: dict) -> str:
    for campo in ("created_at", "date", "updated_at", "due_date"):
        if item.get(campo):
            return str(item[campo])[:10]
    return "sem data"


def main() -> int:
    if not ADVBOX_TOKEN or not ASAAS_TOKEN:
        print("ERRO: ADVBOX_TOKEN e/ou ASAAS_TOKEN não configurados.")
        return 1

    lancs = advbox_contadoria_sem_pagamento()
    vencidos = [l for l in lancs if (l.get("date_due") or "9999")[:10] < HOJE]
    print(f"Advbox CONTADORIA: {len(lancs)} sem data de pagamento, {len(vencidos)} já vencidos.")
    if vencidos:
        print("Campos de um lançamento vencido (só nomes):", sorted(vencidos[0].keys()))

    recebs = recebimentos_asaas()
    print(f"Asaas (desde {INICIO_ASAAS}): {len(recebs)} recebimentos.")

    por_digitos = defaultdict(list)
    for r in recebs:
        ref = digitos(r.get("externalReference"))
        if len(ref) >= 15:
            por_digitos[ref].append(r)

    # --- 1) cruzamento Asaas ---
    com_proc, sem_proc, achados = [], 0, 0
    sem_receb = []
    for l in vencidos:
        proc = digitos(l.get("process_number"))
        if len(proc) < 15:
            sem_proc += 1
            continue
        com_proc.append(l)
        casados = [r for ref, rs in por_digitos.items()
                   if proc in ref or ref.endswith(proc) for r in rs]
        if casados:
            achados += 1
            print(f"  ACHADO {mascarar(proc)} venc {str(l.get('date_due'))[:10]} "
                  f"Advbox {l.get('amount')} | Asaas {[(x.get('date'), x.get('value')) for x in casados][:3]}")
        else:
            sem_receb.append(l)
            print(f"  SEM RECEBIMENTO {mascarar(proc)} venc {str(l.get('date_due'))[:10]} valor {l.get('amount')}")

    print(f"\nResumo vencidos: {len(vencidos)} | sem número de processo: {sem_proc} | "
          f"com processo: {len(com_proc)} | recebimento no Asaas: {achados} | "
          f"sem recebimento no Asaas: {len(sem_receb)}")

    # --- 2) leitura das tarefas do Advbox (dos processos vencidos) ---
    print("\nLEITURA DAS TAREFAS (processos vencidos sem baixa)")
    sem_id = 0
    lidos = 0
    total_itens = 0
    com_palavra = 0
    contagem_palavras = Counter()
    for l in vencidos:
        lid = id_processo(l)
        if not lid:
            sem_id += 1
            continue
        itens = ler_tarefas(lid)
        lidos += 1
        total_itens += len(itens)
        achou = []
        for it in itens:
            txt = texto_do_item(it)
            for m in set(x.lower() for x in PALAVRAS.findall(txt)):
                contagem_palavras[m] += 1
                achou.append((data_do_item(it), m))
        if achou:
            com_palavra += 1
            datas = sorted({d for d, _ in achou})
            palavras = sorted({m for _, m in achou})
            print(f"  TAREFA {mascarar(digitos(l.get('process_number')))} venc {str(l.get('date_due'))[:10]} "
                  f"| itens: {len(itens)} | datas: {datas[:5]} | palavras: {palavras}")

    print(f"\nResumo tarefas: vencidos lidos: {lidos} | sem id de processo: {sem_id} | "
          f"itens lidos: {total_itens} | processos com palavra-chave: {com_palavra}")
    if contagem_palavras:
        print("Palavras (contagem de itens):", dict(contagem_palavras.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
