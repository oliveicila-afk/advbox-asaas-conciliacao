"""Somente leitura: confere os lançamentos gravados pela automação (centro de custo, tese, categoria, valor, datas).
Imprime nomes de categoria/centro/tese (equipe do escritório), nunca nome de cliente, descrição ou número de processo."""
from collections import Counter
import conferir_pendentes as cp
import aplicar_regra_liquido as a

GRAVADOS = {"15071196": "pagamento", "15116112": "pagamento", "15193025": "pagamento",
            "15193032": "pagamento", "15399873": "pagamento", "16912661": "pendente"}


def nomes_configuracao():
    r = cp._get(f"{cp.ADVBOX_BASE}/settings", a.headers())
    dados = r.json().get("data", r.json())
    cats = {str(c.get("id")): c.get("name") or c.get("title") for c in (dados.get("financial") or {}).get("categories", []) or []}
    ccs = {str(c.get("id")): c.get("name") or c.get("title") for c in (dados.get("financial") or {}).get("cost_centers", []) or []}
    return cats, ccs


def main():
    cats, ccs = nomes_configuracao()
    print("CHAVES financial:", sorted((dados_fin := {}).keys()) if False else "")
    r = cp._get(f"{cp.ADVBOX_BASE}/settings", a.headers())
    fin = (r.json().get("data", r.json()) or {}).get("financial") or {}
    print("CHAVES de financial:", sorted(fin.keys()) if isinstance(fin, dict) else type(fin).__name__)
    for tx, tipo in GRAVADOS.items():
        d = a.detalhe(tx)
        cat = str(d.get("categories_id"))
        cc = str(d.get("cost_centers_id"))
        lid = cp.id_processo(d)
        tese = "sem processo"
        if lid:
            rl = cp._get(f"{cp.ADVBOX_BASE}/lawsuits/{lid}", a.headers())
            if rl.status_code == 200:
                L = rl.json().get("data", rl.json())
                tese = str((L.get("type") or {}).get("name") if isinstance(L.get("type"), dict) else L.get("type") or L.get("lawsuit_type") or "?")
        print(f"\nLANÇAMENTO {tx} ({tipo})")
        print(f"  valor={d.get('amount')} venc={str(d.get('date_due'))[:10]} pag={str(d.get('date_payment'))[:10]}")
        print(f"  categoria={cats.get(cat, cat)} | centro_de_custo={ccs.get(cc, cc)} | tese={tese}")
        print(f"  cliente_preenchido={bool(d.get('customers_id'))} | processo_preenchido={bool(lid)} | descricao_tamanho={len(str(d.get('description') or ''))}")
    print("\nREFERÊNCIA: distribuição das categorias e centros de custo nos recebimentos de êxito já baixados:")
    todos, off = [], 0
    while off < 3000:
        rr = cp._get(f"{cp.ADVBOX_BASE}/transactions", a.headers(), {"entry_type": "income", "limit": 500, "offset": off})
        pag = rr.json()
        dados = pag.get("data") or []
        todos += dados
        off += len(dados)
        if not dados or off >= int(pag.get("totalCount", off)):
            break
    exito = [t for t in todos if (t.get("debit_bank") or "").upper() == "CONTADORIA" and t.get("date_payment")
             and "Êxit" in str(cats.get(str(t.get("categories_id")), ""))]
    print("Recebimentos de êxito baixados:", len(exito))
    print("Centros mais usados:", [(ccs.get(str(k), k), n) for k, n in Counter(str(t.get("cost_centers_id")) for t in exito).most_common(4)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
