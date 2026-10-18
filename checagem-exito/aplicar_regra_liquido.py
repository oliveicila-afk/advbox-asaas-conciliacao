"""Regra combinada de recebimento com tolerância de R$ 110 sobre o LÍQUIDO informado nas tarefas.

Classificação de cada lançamento vencido da CONTADORIA que tem recebimento no Asaas:
- ENQUADRA: o valor que caiu está a até R$ 110 de um líquido citado nas tarefas e não há
  movimentação pendente. Ação: preenche só a data de pagamento (data do Asaas). O valor bruto
  do Advbox NÃO muda.
- PENDENTE: há movimentação pendente nas tarefas (falta, complementar, saldo, recurso, etc.).
  Ação: a data de pagamento vira a do Asaas e o valor vira o que caiu no Asaas; cria uma tarefa
  para a Gabi com prazo de 30 dias para verificar o valor restante e a previsão de recebimento.
- NAO ENQUADRA: nada é gravado.

Só grava nos lançamentos em IDS e só se APLICAR=true. Modo padrão: simulação.
Não imprime nomes, textos de tarefas, nem números completos de processo.
"""

import os
import re
import sys
import time
from datetime import date, datetime, timedelta

import requests

import conferir_pendentes as cp

APLICAR = os.environ.get("APLICAR", "false").strip().lower() == "true"
IDS = {i.strip() for i in os.environ.get("IDS", "").split(",") if i.strip()}
TODOS = "*" in IDS  # modo automático: qualquer caso que se enquadre
MAX_GRAVACOES = int(os.environ.get("MAX_GRAVACOES", "25"))  # trava de segurança por execução
TOLERANCIA = 110.0
PRISCILA_ID = 65747
GABI_ID = 178866
TIPO_TAREFA_COBRANCA_EXITO = 9829684  # COMUNIC. FINANCEIRO - COBRANÇA DE ÊXITO

SEGMENTO_LIQUIDO = re.compile(r"l[ií]quid|alvar[áa]", re.IGNORECASE)
VALOR_RS = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})")
PENDENCIA = re.compile(
    r"falta|complementar|saldo|parcela|restante|requer|recurso|cumprimento|intima|expedi|andamento|auditor",
    re.IGNORECASE,
)
FALTA = re.compile(r"falta|complementar", re.IGNORECASE)


def para_float(txt: str) -> float:
    return float(txt.replace(".", "").replace(",", "."))


def valor_advbox(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")  # o Advbox grava com vírgula


def br(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y")


def valores_liquidos(itens: list[dict]) -> list[float]:
    achados = []
    for it in itens:
        for trecho in re.split(r"[\n\r]+|(?<=\.)\s", cp.texto_do_item(it)):
            if SEGMENTO_LIQUIDO.search(trecho):
                achados += [para_float(v) for v in VALOR_RS.findall(trecho)]
    return sorted(set(achados))


def pendencias(itens: list[dict], data_asaas: str) -> list[tuple[str, set]]:
    achados = []
    for it in itens:
        txt = cp.texto_do_item(it)
        kws = {m.lower() for m in PENDENCIA.findall(txt)}
        if not kws:
            continue
        d = cp.data_do_item(it)
        if (d[:10] >= data_asaas) or FALTA.search(txt):
            achados.append((d, kws))
    return achados


def classificar(itens: list[dict], valor_asaas: float, data_asaas: str):
    liquidos = valores_liquidos(itens)
    pend = pendencias(itens, data_asaas)
    if pend:
        return "PENDENTE", liquidos, pend
    enquadra = [v for v in liquidos if abs(v - valor_asaas) <= TOLERANCIA]
    if enquadra:
        return "ENQUADRA", liquidos, []
    return "NAO ENQUADRA", liquidos, []


def headers():
    return {"Authorization": f"Bearer {cp.ADVBOX_TOKEN}", "User-Agent": "Mozilla/5.0",
            "Accept": "application/json", "Content-Type": "application/json"}


def detalhe(tx_id) -> dict:
    resp = cp._get(f"{cp.ADVBOX_BASE}/transactions/{tx_id}", headers())
    resp.raise_for_status()
    corpo = resp.json()
    return corpo.get("data", corpo) if isinstance(corpo, dict) else corpo


def salvar(det: dict, data_pagamento: str, novo_valor: float | None = None) -> bool:
    valor = novo_valor if novo_valor is not None else float(det.get("amount") or 0)
    payload = {
        "entry_type": det.get("entry_type") or "income",
        "users_id": det.get("users_id") or PRISCILA_ID,
        "debit_account": det.get("debit_account"),
        "categories_id": det.get("categories_id"),
        "cost_centers_id": det.get("cost_centers_id"),
        "customers_id": det.get("customers_id"),
        "lawsuits_id": det.get("lawsuits_id"),
        "amount": valor_advbox(valor),
        "date_due": str(det.get("date_due") or "")[:10],
        "date_payment": data_pagamento,
        "description": det.get("description") or "",
    }
    payload = {k: v for k, v in payload.items() if v not in (None, "")}
    resp = requests.put(f"{cp.ADVBOX_BASE}/transactions/{det['id']}", headers=headers(),
                        json=payload, timeout=30)
    time.sleep(2.2)
    return resp.status_code in (200, 204)


def verificar_tarefa(lawsuit_id) -> bool:
    """Confere se existe uma tarefa criada hoje para o processo, atribuída à Gabi (sem ler o texto)."""
    resp = cp._get(f"{cp.ADVBOX_BASE}/posts", headers(), {"lawsuits_id": lawsuit_id, "limit": 100})
    if resp.status_code != 200:
        return False
    corpo = resp.json()
    lista = corpo.get("data", corpo) if isinstance(corpo, dict) else corpo
    hoje = date.today().isoformat()
    for p in lista or []:
        if str(p.get("lawsuits_id") or "") == str(lawsuit_id) and str(p.get("created_at") or "")[:10] == hoje and any(
                (u or {}).get("user_id") == GABI_ID for u in (p.get("users") or [])):
            return True
    return False


def criar_tarefa(lawsuit_id, comentario: str, inicio: str) -> bool:
    payload = {
        "from": PRISCILA_ID,
        "guests": [GABI_ID],
        "tasks_id": TIPO_TAREFA_COBRANCA_EXITO,
        "lawsuits_id": lawsuit_id,
        "start_date": inicio,
        "comments": comentario,
        "important": True,
        "urgent": False,
    }
    resp = requests.post(f"{cp.ADVBOX_BASE}/posts", headers=headers(), json=payload, timeout=30)
    time.sleep(2.2)
    ok = resp.status_code in (200, 201)
    print(f"  tarefa criada: {'OK' if ok else 'FALHOU ' + str(resp.status_code)}")
    if ok:
        print(f"  tarefa verificada no Advbox: {'SIM' if verificar_tarefa(lawsuit_id) else 'NÃO ENCONTRADA'}")
    return ok


def prazo_30_dias(data_recebimento: str) -> str:
    alvo = date.fromisoformat(data_recebimento) + timedelta(days=30)
    if alvo < date.today():
        alvo = date.today() + timedelta(days=30)
        print("  prazo de 30 dias a partir do recebimento já passou; usei 30 dias a partir de hoje")
    return alvo.isoformat()


def main() -> int:
    if not cp.ADVBOX_TOKEN or not cp.ASAAS_TOKEN:
        print("ERRO: tokens não configurados.")
        return 1

    lancs = cp.advbox_contadoria_sem_pagamento()
    vencidos = [l for l in lancs if (l.get("date_due") or "9999")[:10] < cp.HOJE]
    recebs = cp.recebimentos_asaas()
    por_digitos = {}
    for r in recebs:
        ref = cp.digitos(r.get("externalReference"))
        if len(ref) >= 15:
            por_digitos.setdefault(ref, []).append(r)

    casos = []
    for l in vencidos:
        proc = cp.digitos(l.get("process_number"))
        if len(proc) < 15:
            continue
        casados = [r for ref, rs in por_digitos.items() if proc in ref or ref.endswith(proc) for r in rs]
        if casados:
            casos.append((l, proc, casados))
    print(f"Casos com recebimento no Asaas: {len(casos)}")

    gravacoes = 0
    for l, proc, casados in casos:
        tx_id = str(l.get("id"))
        r = casados[0]
        valor_asaas = float(r.get("value") or 0)
        data_asaas = str(r.get("date") or "")[:10]
        bruto = float(l.get("amount") or 0)
        lid = cp.id_processo(l)
        itens = cp.ler_tarefas(lid) if lid else []
        decisao, liquidos, pend = classificar(itens, valor_asaas, data_asaas)
        print(f"\nCASO id={tx_id} processo={cp.mascarar(proc)} venc={str(l.get('date_due'))[:10]} "
              f"bruto={bruto:.2f} asaas={valor_asaas:.2f} em={data_asaas}")
        print(f"  líquidos citados nas tarefas: {[round(v, 2) for v in liquidos]}")
        if pend:
            print(f"  movimentações pendentes: {len(pend)} | palavras: {sorted({k for _, s in pend for k in s})}")
        print(f"  decisão: {decisao}")

        if not (APLICAR and (TODOS or tx_id in IDS)):
            continue
        if gravacoes >= MAX_GRAVACOES:
            print(f"  limite de {MAX_GRAVACOES} gravações nesta execução atingido; caso fica para a próxima")
            continue
        det = detalhe(tx_id)
        if float(det.get("amount") or 0) != bruto:
            print("  ABORTADO: valor do lançamento mudou antes da gravação")
            continue

        if decisao == "ENQUADRA":
            ok = salvar(det, data_asaas)
            depois = detalhe(tx_id)
            gravacoes += 1
            print(f"  GRAVAÇÃO data: {'OK' if ok else 'FALHOU'} | data={str(depois.get('date_payment'))[:10]} "
                  f"| bruto mantido={float(depois.get('amount') or 0) == bruto}")
        elif decisao == "PENDENTE":
            ok = salvar(det, data_asaas, novo_valor=valor_asaas)
            depois = detalhe(tx_id)
            gravacoes += 1
            print(f"  GRAVAÇÃO pendente: {'OK' if ok else 'FALHOU'} | data={str(depois.get('date_payment'))[:10]} "
                  f"| valor agora={float(depois.get('amount') or 0):.2f}")
            if ok and lid:
                comentario = (
                    f"Pagamento recebido em {br(data_asaas)} com valor a menor. "
                    f"Valor bruto no Advbox: R$ {valor_advbox(bruto)}. "
                    f"Valor recebido: R$ {valor_advbox(valor_asaas)}. "
                    "Processo com movimentação após o pagamento. Verificar se falta valor a receber, "
                    "a previsão de data e a possível incidência de juros e multa."
                )
                criar_tarefa(lid, comentario, prazo_30_dias(data_asaas))
        else:
            print("  não gravado: não enquadra")
    print(f"\nResumo: gravações nesta execução = {gravacoes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
