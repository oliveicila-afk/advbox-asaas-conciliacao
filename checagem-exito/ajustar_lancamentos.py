"""Ajusta categoria e centro de custo de lançamentos já gravados, conforme regras combinadas.
Padrão: simulação (APLICAR=false). Com APLICAR=true, grava e confere a leitura de volta.
Não imprime nomes de clientes, descrições nem números de processo: só percentuais encontrados."""
import os
import re
import sys
import time
import unicodedata

import requests

import conferir_pendentes as cp
import aplicar_regra_liquido as a

APLICAR = os.environ.get("APLICAR", "false").strip().lower() == "true"
CENTRO_PM_AM_TRAFEGO = "PM/AM-TRÁFEGO PAGO"
SUCUMBENCIAL_ITEM_B = ["sucumbenc", "item b"]
GRATIFICACAO = ["15071196", "15193032", "15399873"]  # centro -> PM/AM-TRÁFEGO PAGO
SOMENTE_CATEGORIA = ["16912661"]  # sucumbencial item B, se a descrição for 100%
PERCENTUAL = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s?%")


def norm(s) -> str:
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()


def ler_todos():
    todos, off = [], 0
    while True:
        rr = cp._get(f"{cp.ADVBOX_BASE}/transactions", a.headers(), {"entry_type": "income", "limit": 500, "offset": off})
        pag = rr.json()
        lote = pag.get("data") or []
        todos += lote
        off += len(lote)
        if not lote or off >= int(pag.get("totalCount", off)) or off > 20000:
            break
        time.sleep(2.2)
    return todos


def mapear(todos):
    cats, ccs = {}, {}
    for t in todos:
        if t.get("categories_id") and isinstance(t.get("category"), str):
            cats.setdefault(t["category"].strip(), t["categories_id"])
        if t.get("cost_centers_id") and isinstance(t.get("cost_center"), str):
            ccs.setdefault(t["cost_center"].strip(), t["cost_centers_id"])
    return cats, ccs


def achar(mapa, termos, rotulo):
    cand = [n for n in mapa if all(t in norm(n) for t in termos)]
    if len(cand) != 1:
        print(f"{rotulo}: {len(cand)} candidatos {cand[:6]} -> abortado")
        return None
    print(f"{rotulo}: '{cand[0]}' (id {mapa[cand[0]]})")
    return mapa[cand[0]]


def gravar(tx, nome_cat, id_cat, nome_cc, id_cc, bruto_esperado=None):
    antes = a.detalhe(tx)
    bruto = float(antes.get("amount") or 0)
    if not APLICAR:
        print(f"SIMULAÇÃO {tx}: categoria -> {nome_cat} | centro -> {nome_cc} | valor {bruto:.2f} mantido")
        return
    payload = {
        "entry_type": antes.get("entry_type") or "income",
        "users_id": antes.get("users_id") or a.PRISCILA_ID,
        "debit_account": antes.get("debit_account"),
        "categories_id": id_cat or antes.get("categories_id"),
        "cost_centers_id": id_cc or antes.get("cost_centers_id"),
        "customers_id": antes.get("customers_id"),
        "lawsuits_id": antes.get("lawsuits_id"),
        "amount": a.valor_advbox(bruto),
        "date_due": str(antes.get("date_due") or "")[:10],
        "date_payment": str(antes.get("date_payment") or "")[:10],
        "description": antes.get("description") or "",
    }
    payload = {k: v for k, v in payload.items() if v not in (None, "")}
    resp = requests.put(f"{cp.ADVBOX_BASE}/transactions/{tx}", headers=a.headers(), json=payload, timeout=30)
    time.sleep(2.2)
    depois = a.detalhe(tx)
    ok = (
        resp.status_code in (200, 204)
        and str(depois.get("categories_id")) == str(payload["categories_id"])
        and str(depois.get("cost_centers_id")) == str(payload["cost_centers_id"])
        and float(depois.get("amount") or 0) == bruto
        and str(depois.get("date_payment"))[:10] == str(antes.get("date_payment"))[:10]
    )
    print(f"GRAVADO {tx}: {'CONFERIDO' if ok else 'NÃO CONFERIU (HTTP ' + str(resp.status_code) + ')'} | "
          f"categoria -> {nome_cat} | centro -> {nome_cc} | valor {bruto:.2f} | data pagamento preservada")


def main() -> int:
    if not cp.ADVBOX_TOKEN:
        print("ERRO: ADVBOX_TOKEN não configurado.")
        return 1
    print("Modo:", "GRAVAÇÃO" if APLICAR else "SIMULAÇÃO")
    todos = ler_todos()
    cats, ccs = mapear(todos)
    print(f"Nomes lidos: {len(cats)} categorias, {len(ccs)} centros")
    id_pm = achar(ccs, [norm(CENTRO_PM_AM_TRAFEGO)], "centro PM/AM-TRÁFEGO PAGO") if norm(CENTRO_PM_AM_TRAFEGO) in map(norm, ccs) else None
    if not id_pm:
        print("ERRO: centro PM/AM-TRÁFEGO PAGO não encontrado; nada foi gravado.")
        return 1
    id_suc = achar(cats, SUCUMBENCIAL_ITEM_B, "categoria sucumbencial item B")
    if not id_suc:
        print("ERRO: categoria sucumbencial item B não encontrada de forma única; nada foi gravado.")
        return 1
    nome_suc = next(n for n, i in cats.items() if i == id_suc)

    for tx in GRATIFICACAO:
        gravar(tx, None, None, CENTRO_PM_AM_TRAFEGO, id_pm)

    for tx in SOMENTE_CATEGORIA:
        det = a.detalhe(tx)
        percentuais = [float(p.replace(",", ".")) for p in PERCENTUAL.findall(str(det.get("description") or ""))]
        print(f"{tx}: percentuais na descrição: {percentuais}")
        if percentuais and all(p == 100 for p in percentuais):
            gravar(tx, nome_suc, id_suc, None, None)
        else:
            print(f"{tx}: NÃO ALTERADO (descrição sem 100% exclusivo; decidir se é compartilhado com o cliente)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
