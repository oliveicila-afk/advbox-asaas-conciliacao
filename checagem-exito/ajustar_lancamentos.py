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
GRATIFICACAO = ["15071196", "15193032", "15399873"]  # centro -> PM/AM-TRÁFEGO PAGO
ESCALONAMENTO = ["15116112"]  # centro -> ESCALONAMENTO PC/AM-TRÁFEGO PAGO
SOMENTE_CATEGORIA = ["16912661"]  # categoria -> sucumbencial item B, se a descrição for 100%
PERCENTUAL = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s?%")


def norm(s) -> str:
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()


def achar_no_cadastro(itens, criterio, rotulo):
    achados = []
    for c in itens or []:
        textos = [v for v in c.values() if isinstance(v, str)]
        if any(criterio(norm(t)) for t in textos):
            achados.append((c.get("id"), next(t for t in textos if criterio(norm(t)))))
    print(f"{rotulo}: {len(achados)} encontrado(s)")
    return achados


def gravar(tx, nome_cat, id_cat, nome_cc, id_cc):
    antes = a.detalhe(tx)
    bruto = float(antes.get("amount") or 0)
    if not APLICAR:
        print(f"SIMULAÇÃO {tx}: categoria -> {nome_cat or 'sem mudança'} | "
              f"centro -> {nome_cc or 'sem mudança'} | valor {bruto:.2f} mantido")
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
          f"categoria -> {nome_cat or 'sem mudança'} | centro -> {nome_cc or 'sem mudança'} | "
          f"valor {bruto:.2f} e data de pagamento preservados")


def main() -> int:
    if not cp.ADVBOX_TOKEN:
        print("ERRO: ADVBOX_TOKEN não configurado.")
        return 1
    print("Modo:", "GRAVAÇÃO" if APLICAR else "SIMULAÇÃO")
    r = cp._get(f"{cp.ADVBOX_BASE}/settings", a.headers())
    dados = r.json().get("data", r.json())
    fin = dados.get("financial") or {}
    print("Chaves de uma categoria do cadastro:", sorted(fin["categories"][0].keys()) if fin.get("categories") else "-")

    ccs = achar_no_cadastro(fin.get("cost_centers"), lambda t: t == norm(CENTRO_PM_AM_TRAFEGO), "centro PM/AM-TRÁFEGO PAGO")
    cats = achar_no_cadastro(fin.get("categories"), lambda t: "sucumbenc" in t and "item b" in t,
                             "categoria sucumbencial item B")
    if len(ccs) != 1 or len(cats) != 1:
        print("ERRO: cadastro ambíguo ou não encontrado; nada foi gravado.")
        return 1
    id_pm, nome_pm = ccs[0]
    id_suc, nome_suc = cats[0]
    print(f"Usando: centro id {id_pm} | categoria id {id_suc}")
    esc = achar_no_cadastro(fin.get("cost_centers"), lambda t: t == norm("ESCALONAMENTO PC/AM-TRÁFEGO PAGO"),
                            "centro ESCALONAMENTO PC/AM-TRÁFEGO PAGO")
    if len(esc) != 1:
        print("ERRO: centro de escalonamento ambíguo ou não encontrado; nada foi gravado.")
        return 1
    id_esc, nome_esc = esc[0]

    for tx in GRATIFICACAO:
        gravar(tx, None, None, nome_pm, id_pm)

    for tx in ESCALONAMENTO:
        gravar(tx, None, None, nome_esc, id_esc)

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
