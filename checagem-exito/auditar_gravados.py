"""Somente leitura (diagnóstico): confere os lançamentos gravados pela automação e descobre
qual categoria e centro de custo a equipe usa nos recebimentos de êxito já baixados.
Imprime nomes de categoria/centro (cadastro do escritório), nunca nome de cliente, descrição ou número de processo."""
import unicodedata
from collections import Counter

import conferir_pendentes as cp
import aplicar_regra_liquido as a

GRAVADOS = {"15071196": "pagamento", "15116112": "pagamento", "15193025": "pagamento",
            "15193032": "pagamento", "15399873": "pagamento", "16912661": "pendente"}


def norm(s) -> str:
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def main():
    r = cp._get(f"{cp.ADVBOX_BASE}/settings", a.headers())
    dados = r.json().get("data", r.json())
    fin = dados.get("financial") or {}
    cats = {str(c.get("id")): c.get("name") or c.get("title") for c in fin.get("categories") or []}
    ccs = {str(c.get("id")): c.get("name") or c.get("title") for c in fin.get("cost_centers") or []}
    print(f"CATEGORIAS cadastradas: {len(cats)} | CENTROS cadastrados: {len(ccs)}")
    print("CATEGORIAS com 'exito' no nome:", [v for k, v in cats.items() if "exit" in norm(v)][:10])

    for tx, tipo in GRAVADOS.items():
        d = a.detalhe(tx)
        cat_obj = d.get("category") if isinstance(d.get("category"), dict) else {}
        cc_obj = d.get("cost_center") if isinstance(d.get("cost_center"), dict) else {}
        print(f"LANÇAMENTO {tx} ({tipo}): categoria={cat_obj.get('name') or cat_obj.get('title') or d.get('category')} "
              f"| centro_de_custo={cc_obj.get('name') or cc_obj.get('title') or d.get('cost_center')} "
              f"| chaves_centro={sorted(cc_obj.keys())[:8]}")

    todos, off = [], 0
    while off < 5000:
        rr = cp._get(f"{cp.ADVBOX_BASE}/transactions", a.headers(),
                     {"entry_type": "income", "limit": 500, "offset": off})
        pag = rr.json()
        dados = pag.get("data") or []
        todos += dados
        off += len(dados)
        if not dados or off >= int(pag.get("totalCount", off)):
            break
    print(f"Receitas lidas no Advbox: {len(todos)} de {pag.get('totalCount')}")
    print("Contas (debit_bank) mais frequentes:", Counter(str(t.get("debit_bank")) for t in todos).most_common(6))
    contexto = [t for t in todos if (t.get("debit_bank") or "").upper() == "CONTADORIA" and t.get("date_payment")]
    print(f"Receitas da CONTADORIA já baixadas: {len(contexto)}")
    if contexto:
        print("Campos de uma baixada (só nomes):", sorted(contexto[0].keys()))
    print("Categorias mais usadas:", [(cats.get(str(k), k), n) for k, n in
                                     Counter(str(t.get("categories_id")) for t in contexto).most_common(6)])
    print("Centros mais usados:", [(ccs.get(str(k), k), n) for k, n in
                                  Counter(str(t.get("cost_centers_id")) for t in contexto).most_common(6)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
