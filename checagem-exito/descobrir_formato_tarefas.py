"""Somente leitura: descobre o formato das tarefas (/posts) e dos usuários (/users) do Advbox.
Imprime só nomes de campos, tipos e contagens. Não imprime textos, nomes de clientes nem processos.
"""
import re
import conferir_pendentes as cp


def tipo(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "num"
    if isinstance(v, str):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", v):
            return "data-iso"
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}.*", v):
            return "data-br"
        return f"str(len~{min(len(v)//20*20, 200)})"
    if isinstance(v, list):
        return f"list({len(v)})"
    if isinstance(v, dict):
        return "obj{" + ",".join(sorted(v.keys()))[:300] + "}"
    return type(v).__name__


def resumo(item):
    return {k: tipo(v) for k, v in sorted(item.items())}


def get(caminho, params=None):
    r = cp._get(f"{cp.ADVBOX_BASE}{caminho}", cp._advbox_headers(), params)
    print(f"GET {caminho} -> {r.status_code}")
    if r.status_code != 200:
        print("  corpo (início):", r.text[:150].replace("\n", " "))
        return None
    corpo = r.json()
    return corpo.get("data", corpo) if isinstance(corpo, dict) else corpo


def main():
    if not cp.ADVBOX_TOKEN:
        print("ERRO: ADVBOX_TOKEN não configurado")
        return 1
    posts = get("/posts", {"limit": 5})
    if isinstance(posts, list) and posts:
        print("CAMPOS de /posts:", resumo(posts[0]))
        print("Quantidade na página:", len(posts))
    usuarios = get("/users", {"limit": 200})
    if isinstance(usuarios, list):
        print("Quantidade de usuários:", len(usuarios))
        if usuarios:
            print("CAMPOS de /users:", resumo(usuarios[0]))
        for u in usuarios:
            nome = str(u.get("name") or "")
            if nome.lower().startswith("gabi"):
                print("USUÁRIO encontrado com prefixo 'Gabi': id =", u.get("id"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
