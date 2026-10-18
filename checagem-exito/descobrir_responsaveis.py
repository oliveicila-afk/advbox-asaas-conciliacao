"""Somente leitura: lista os responsáveis das tarefas (nomes de equipe, sem clientes) e seus ids."""
from collections import Counter
import conferir_pendentes as cp


def main():
    todos, offset = [], 0
    while offset < 1000:
        r = cp._get(f"{cp.ADVBOX_BASE}/posts", cp._advbox_headers(), {"limit": 100, "offset": offset})
        if r.status_code != 200:
            print("posts ->", r.status_code)
            break
        pag = r.json()
        dados = pag.get("data", pag) if isinstance(pag, dict) else pag
        if not dados:
            break
        todos += dados
        offset += len(dados)
    cont, ids = Counter(), {}
    for p in todos:
        for u in p.get("users") or []:
            nome = str(u.get("name") or "").strip()
            ids[nome] = u.get("user_id")
            cont[nome] += 1
    print("Responsáveis distintos:", len(cont))
    for nome, n in cont.most_common(30):
        print(f"RESPONSAVEL {nome.split(' ')[0] if nome else '(vazio)'} user_id={ids.get(nome)} tarefas={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
