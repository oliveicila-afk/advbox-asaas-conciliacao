"""Somente leitura (diagnóstico): compara a categoria e o centro de custo dos lançamentos gravados
pela automação com os recebimentos de êxito da CONTADORIA já baixados.
Imprime nomes de categoria e centro (cadastro do escritório), nunca nome de cliente, descrição ou processo."""
import unicodedata
from collections import Counter, defaultdict

import conferir_pendentes as cp
import aplicar_regra_liquido as a

GRAVADOS = {"15071196": "pagamento", "15116112": "pagamento", "15193025": "pagamento",
            "15193032": "pagamento", "15399873": "pagamento", "16912661": "pendente"}


def norm(s) -> str:
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def nome(obj):
    if isinstance(obj, dict):
        for k in ("name", "title", "description"):
            if obj.get(k):
                return str(obj[k])
    return None


def main():
    r = cp._get(f"{cp.ADVBOX_BASE}/settings", a.headers())
    dados = r.json().get("data", r.json())
    fin = dados.get("financial") or {}
    cats = {str(c.get("id")): nome(c) for c in fin.get("categories") or []}
    ccs = {str(c.get("id")): nome(c) for c in fin.get("cost_centers") or []}
    print(f"Cadastro: {len(cats)} categorias, {len(ccs)} centros; nomes resolvidos: "
          f"{sum(1 for v in cats.values() if v)} categorias, {sum(1 for v in ccs.values() if v)} centros")

    atual = {}
    for tx, tipo in GRAVADOS.items():
        d = a.detalhe(tx)
        cat = nome(d.get("category")) or cats.get(str(d.get("categories_id")))
        cc = nome(d.get("cost_center")) or ccs.get(str(d.get("cost_centers_id")))
        atual[tx] = (cat, cc)
        print(f"LANÇAMENTO {tx} ({tipo}): categoria={cat} | centro_de_custo={cc}")

    todos, off = [], 0
    while True:
        rr = cp._get(f"{cp.ADVBOX_BASE}/transactions", a.headers(),
                     {"entry_type": "income", "limit": 500, "offset": off})
        pag = rr.json()
        lote = pag.get("data") or []
        todos += lote
        off += len(lote)
        if not lote or off >= int(pag.get("totalCount", off)) or off > 20000:
            break
        time_sleep = __import__("time").sleep
        time_sleep(2.2)
    print(f"Receitas lidas: {len(todos)} de {pag.get('totalCount')}")
    if todos:
        print("Campos de uma receita (só nomes):", sorted(todos[0].keys()))

    contexto = [t for t in todos if (t.get("debit_bank") or "").upper() == "CONTADORIA" and t.get("date_payment")]
    pares = []
    for t in contexto:
        c = nome(t.get("category")) or cats.get(str(t.get("categories_id")))
        k = nome(t.get("cost_center")) or ccs.get(str(t.get("cost_centers_id")))
        if c and "exit" in norm(c):
            pares.append((c, k))
    print(f"CONTADORIA já baixadas: {len(contexto)} | de êxito com categoria identificada: {len(pares)}")

    por_cat = defaultdict(Counter)
    for c, k in pares:
        por_cat[c][k] += 1
    for tx, (cat, cc) in atual.items():
        usados = por_cat.get(cat, Counter())
        total = sum(usados.values())
        print(f"\nREF {tx}: categoria usada em {total} recebimentos baixados | centro do lançamento: {cc}")
        print(f"  centros usados com essa categoria: {usados.most_common(4)}")
    print("\nTodas as categorias de êxito baixadas (top 12):", por_cat and [(c, sum(v.values())) for c, v in
          sorted(por_cat.items(), key=lambda x: -sum(x[1].values()))[:12]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
