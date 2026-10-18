"""Somente leitura: procura o id da Gabi em caminhos de usuários/equipe. Imprime status e ids, não dados."""
import conferir_pendentes as cp

CAMINHOS = ["/users", "/users/", "/settings/users", "/settings/team", "/team", "/employees", "/settings/employees", "/collaborators"]


def main():
    for c in CAMINHOS:
        r = cp._get(f"{cp.ADVBOX_BASE}{c}", cp._advbox_headers(), {"limit": 200})
        print(f"CAMINHO {c} -> {r.status_code}")
        if r.status_code != 200:
            continue
        corpo = r.json()
        lista = corpo.get("data", corpo) if isinstance(corpo, dict) else corpo
        if not isinstance(lista, list):
            print("  formato não é lista")
            continue
        print(f"  itens: {len(lista)} | chaves: {sorted(lista[0].keys()) if lista and isinstance(lista[0], dict) else '-'}")
        for u in lista:
            if isinstance(u, dict):
                nome = str(u.get("name") or u.get("nome") or "").lower()
                if nome.startswith(("gabi", "gabr")):
                    print(f"  ID ENCONTRADO: {u.get('id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
