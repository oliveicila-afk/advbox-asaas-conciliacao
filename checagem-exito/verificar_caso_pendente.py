"""Somente leitura: confere a tarefa criada hoje para o processo pendente (ids, datas e tipo; sem texto)."""
import aplicar_regra_liquido as a
import conferir_pendentes as cp

TX = "16912661"


def main():
    det = a.detalhe(TX)
    lid = cp.id_processo(det)
    print(f"LANÇAMENTO valor={det.get('amount')} data_pagamento={str(det.get('date_payment'))[:10]}")
    todas, off = [], 0
    while True:
        r = cp._get(f"{cp.ADVBOX_BASE}/posts", a.headers(), {"lawsuits_id": lid, "limit": 100, "offset": off})
        corpo = r.json()
        lista = corpo.get("data", corpo) if isinstance(corpo, dict) else corpo
        if not lista:
            break
        todas += lista
        off += len(lista)
        if len(lista) < 100:
            break
    print(f"TAREFAS do processo (todas as páginas): {len(todas)}")
    hoje = [p for p in todas if str(p.get("created_at") or "")[:10] == "2026-10-18"]
    print(f"TAREFAS criadas hoje: {len(hoje)}")
    for p in hoje:
        ids = [(u or {}).get("user_id") for u in (p.get("users") or [])]
        print(f"  TAREFA id={p.get('id')} tipo={p.get('task')} responsaveis_ids={ids} "
              f"gabi_na_lista={a.GABI_ID in ids} date={str(p.get('date'))[:10]} prazo={str(p.get('date_deadline'))[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
