"""Somente leitura: tipos de tarefa e usuários disponíveis em /settings. Imprime ids e nomes de tipos/equipe, nunca clientes."""
import conferir_pendentes as cp


def main():
    r = cp._get(f"{cp.ADVBOX_BASE}/settings", cp._advbox_headers())
    print("GET /settings ->", r.status_code)
    if r.status_code != 200:
        print("  corpo:", r.text[:120])
        return 0
    corpo = r.json()
    dados = corpo.get("data", corpo) if isinstance(corpo, dict) else corpo
    if isinstance(dados, dict):
        print("CHAVES de /settings:", sorted(dados.keys()))
        for chave in dados:
            v = dados[chave]
            if isinstance(v, list):
                print(f"  {chave}: lista com {len(v)} itens")
        for chave in ("task_types", "tasks_types", "tasks", "users"):
            for item in dados.get(chave, []) or []:
                if isinstance(item, dict):
                    nome = str(item.get("name") or item.get("title") or "")
                    print(f"  {chave} id={item.get('id')} nome={nome[:60]}")
    for c in ("/users", "/settings/users"):
        r2 = cp._get(f"{cp.ADVBOX_BASE}{c}", cp._advbox_headers(), {"limit": 200})
        print(f"GET {c} -> {r2.status_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
