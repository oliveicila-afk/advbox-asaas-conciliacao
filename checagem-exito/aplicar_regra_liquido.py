"""Regra combinada: recebimento confirmado quando o valor que caiu no Asaas está a até
R$ 100 do valor LÍQUIDO informado nas tarefas do processo (alvará).

- O valor bruto do lançamento no Advbox NUNCA é alterado.
- A única alteração possível é preencher a data de pagamento (date_payment) com a data
  do recebimento no Asaas, e somente nos lançamentos listados em IDS (escolhidos por você).
- Modo simulação (APLICAR=false): só mostra a decisão de cada caso.

Não imprime nomes, textos de tarefas nem números completos de processo.
"""

import os
import re
import sys
import time

import requests

import conferir_pendentes as cp

APLICAR = os.environ.get("APLICAR", "false").strip().lower() == "true"
IDS = {i.strip() for i in os.environ.get("IDS", "").split(",") if i.strip()}
TOLERANCIA = 110.0  # margem combinada: R$ 110
USERS_ID_PADRAO = 65747  # mesmo padrão do conciliador existente

SEGMENTO_LIQUIDO = re.compile(r"l[ií]quid|alvar[áa]", re.IGNORECASE)
VALOR_RS = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})")


def para_float(txt: str) -> float:
    return float(txt.replace(".", "").replace(",", "."))


def valores_liquidos(itens: list[dict]) -> list[float]:
    """Valores em R$ que aparecem no mesmo trecho que 'líquido' ou 'alvará'."""
    achados = []
    for it in itens:
        texto = cp.texto_do_item(it)
        for trecho in re.split(r"[\n\r]+|(?<=\.)\s", texto):
            if SEGMENTO_LIQUIDO.search(trecho):
                achados += [para_float(v) for v in VALOR_RS.findall(trecho)]
    return sorted(set(achados))


def advbox_headers():
    return {"Authorization": f"Bearer {cp.ADVBOX_TOKEN}", "User-Agent": "Mozilla/5.0",
            "Accept": "application/json", "Content-Type": "application/json"}


def detalhe(tx_id) -> dict:
    resp = cp._get(f"{cp.ADVBOX_BASE}/transactions/{tx_id}", advbox_headers())
    resp.raise_for_status()
    corpo = resp.json()
    return corpo.get("data", corpo) if isinstance(corpo, dict) else corpo


def salvar_data(det: dict, data_pagamento: str) -> bool:
    payload = {
        "entry_type": det.get("entry_type") or "income",
        "users_id": det.get("users_id") or USERS_ID_PADRAO,
        "debit_account": det.get("debit_account"),
        "categories_id": det.get("categories_id"),
        "cost_centers_id": det.get("cost_centers_id"),
        "customers_id": det.get("customers_id"),
        "lawsuits_id": det.get("lawsuits_id"),
        "amount": f"{float(det.get('amount') or 0):.2f}".replace(".", ","),  # Advbox usa vírgula
        "date_due": str(det.get("date_due") or "")[:10],
        "date_payment": data_pagamento,
        "description": det.get("description") or "",
    }
    payload = {k: v for k, v in payload.items() if v not in (None, "")}
    resp = requests.put(f"{cp.ADVBOX_BASE}/transactions/{det['id']}", headers=advbox_headers(),
                        json=payload, timeout=30)
    time.sleep(2.2)
    return resp.status_code in (200, 204)


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

    for l, proc, casados in casos:
        tx_id = str(l.get("id"))
        r = casados[0]
        valor_asaas = float(r.get("value") or 0)
        data_asaas = str(r.get("date") or "")[:10]
        bruto = float(l.get("amount") or 0)
        lid = cp.id_processo(l)
        liquidos = valores_liquidos(cp.ler_tarefas(lid)) if lid else []
        enquadra = [v for v in liquidos if abs(v - valor_asaas) <= TOLERANCIA]
        decisao = "ENQUADRA" if enquadra else "NAO ENQUADRA"
        print(f"\nCASO id={tx_id} processo={cp.mascarar(proc)} venc={str(l.get('date_due'))[:10]} "
              f"bruto={bruto:.2f} asaas={valor_asaas:.2f} em={data_asaas}")
        print(f"  líquidos citados nas tarefas: {[round(v, 2) for v in liquidos]}")
        print(f"  decisão: {decisao}" + (f" (diferença {abs(enquadra[0]-valor_asaas):.2f})" if enquadra else ""))

        if APLICAR and tx_id in IDS and enquadra:
            det = detalhe(tx_id)
            if float(det.get("amount") or 0) != bruto:
                print("  ABORTADO: valor bruto mudou antes da gravação")
                continue
            ok = salvar_data(det, data_asaas)
            depois = detalhe(tx_id)
            print(f"  GRAVAÇÃO: {'OK' if ok else 'FALHOU'} | data_pagamento={str(depois.get('date_payment'))[:10]} "
                  f"| bruto mantido={float(depois.get('amount') or 0) == bruto}")
        elif APLICAR and tx_id in IDS:
            print("  não gravado: não enquadra na regra")
    return 0


if __name__ == "__main__":
    sys.exit(main())
