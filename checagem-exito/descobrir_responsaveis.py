"""Somente leitura: como as tarefas guardam responsável e prazo. Não imprime textos nem nomes de clientes."""
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
    print("Tarefas lidas:", len(todos))
    com_prazo = [p for p in todos if p.get("date_deadline")]
    print("Com prazo (date_deadline):", len(com_prazo))
    if com_prazo:
        print("Formato do prazo (exemplo, só o tipo):", str(com_prazo[0]["date_deadline"])[:4] + "-xx-xx" if str(com_prazo[0]["date_deadline"])[:4].isdigit() else "outro")
    exemplo = next((p for p in todos if p.get("users")), None)
    if exemplo:
        print("Tipo de 'users':", type(exemplo["users"]).__name__, "| primeiro item:", type(exemplo["users"][0]).__name__)
        if isinstance(exemplo["users"][0], dict):
            print("Chaves do usuário na tarefa:", sorted(exemplo["users"][0].keys()))
    ids = {}
    for p in todos:
        for u in p.get("users") or []:
            if isinstance(u, dict):
                nome = str(u.get("name") or "")
                if nome.lower().startswith(("gabi", "gabr")):
                    pass
                if nome.lower().startswith(("gabi", "gabr")):
                    ids[u.get("id")] = True
    print("IDs de usuário com nome Gabi/Gabriele:", list(ids.keys()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
