"""Somente leitura: ids da Gabi e da Priscila em /settings/users, e tipos de tarefa com a palavra ARQUIVAMENTO/PROTOCOLO.
Imprime só ids, campos e nomes de tipos de tarefa (não clientes)."""
import conferir_pendentes as cp


def main():
    r = cp._get(f"{cp.ADVBOX_BASE}/settings", cp._advbox_headers())
    if r.status_code != 200:
        print("settings ->", r.status_code)
        return 0
    corpo = r.json()
    dados = corpo.get("data", corpo) if isinstance(corpo, dict) else corpo
    usuarios = dados.get("users") or []
    tipos = dados.get("tasks") or []
    if usuarios:
        print("CAMPOS de users:", sorted(usuarios[0].keys()))
    if tipos:
        print("CAMPOS de tasks:", sorted(tipos[0].keys()))
    for u in usuarios:
        nome = str(u.get("name") or u.get("full_name") or u.get("nome") or "").lower()
        if nome.startswith(("gabi", "gabr")):
            print("USUARIO gabi id =", u.get("id"))
        if nome.startswith("priscila"):
            print("USUARIO priscila id =", u.get("id"))
    campo = next((k for k in ("name", "task", "title", "description") if tipos and k in tipos[0]), None)
    print("campo de nome do tipo:", campo)
    for t in tipos:
        nome = str(t.get(campo) or "") if campo else ""
        if any(p in nome.upper() for p in ("ARQUIV", "PROTOCOL", "FINANCEIR", "GERAL")):
            print(f"TIPO id={t.get('id')} palavra_encontrada={[p for p in ('ARQUIV','PROTOCOL','FINANCEIR','GERAL') if p in nome.upper()]} nome={nome[:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
