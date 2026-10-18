"""Somente leitura: confere o lançamento pendente já gravado e a tarefa criada para a Gabi."""
import aplicar_regra_liquido as a
import conferir_pendentes as cp

TX = "16912661"


def main():
    det = a.detalhe(TX)
    print(f"LANÇAMENTO valor={det.get('amount')} data_pagamento={str(det.get('date_payment'))[:10]} "
          f"vencimento={str(det.get('date_due'))[:10]} conta={det.get('debit_bank')}")
    lid = cp.id_processo(det)
    if not lid:
        print("sem id de processo no lançamento")
        return 0
    r = cp._get(f"{cp.ADVBOX_BASE}/posts", a.headers(), {"lawsuits_id": lid, "limit": 100})
    corpo = r.json()
    lista = corpo.get("data", corpo) if isinstance(corpo, dict) else corpo
    print(f"TAREFAS do processo: {len(lista or [])}")
    for p in lista or []:
        if any((u or {}).get("user_id") == a.GABI_ID for u in (p.get("users") or [])):
            print(f"  TAREFA DA GABI criada em {str(p.get('created_at'))[:10]} | date={str(p.get('date'))[:10]} "
                  f"| prazo={str(p.get('date_deadline'))[:10]} | tipo={p.get('task')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
