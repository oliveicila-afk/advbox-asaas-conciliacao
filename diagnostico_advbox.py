#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico SÓ-LEITURA da API do Advbox.

NÃO lança, NÃO edita, NÃO cria nada. Só faz GET e imprime:
  1. As categorias e centros de custo do escritório COM os IDs numéricos
     (vindos de /settings) — para montar o de-para nome -> ID no lançamento.
  2. O status de cada caminho candidato de "tarefas do processo", para
     descobrir qual o Advbox aceita (hoje o código usa /lawsuits/{id}/tasks,
     que devolve 401).

Segurança: imprime só configuração (nomes/IDs de categorias e centros de custo)
e códigos de status. Não imprime conteúdo de tarefas (que pode ter dado de
cliente). Usa a MESMA autenticação (Bearer) do conciliar_v2.py.
"""

import os
import json
import requests

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
HEADERS = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": UA, "Accept": "application/json"}

# Processo de exemplo (um dos que deu 401 no dia 28) só para testar o caminho.
PROCESSO_EXEMPLO = os.environ.get("PROCESSO_EXEMPLO", "5836169")


def tenta_get(path, params=None):
    url = f"{ADVBOX_BASE}{path}"
    try:
        r = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
        return r.status_code, r
    except requests.RequestException as e:
        return None, str(e)


def resumo_estrutura(obj, prof=0):
    """Mostra só as CHAVES e tipos, sem despejar valores sensíveis."""
    if isinstance(obj, dict):
        return {k: resumo_estrutura(v, prof + 1) for k, v in list(obj.items())[:40]}
    if isinstance(obj, list):
        return [f"lista com {len(obj)} itens"] + (
            [resumo_estrutura(obj[0], prof + 1)] if obj else []
        )
    return type(obj).__name__


def achar_listas_com_id_e_nome(obj, caminho="root", achados=None):
    """Procura listas de dicts que tenham um campo de id e um de nome."""
    if achados is None:
        achados = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            achar_listas_com_id_e_nome(v, f"{caminho}.{k}", achados)
    elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
        chaves = set(obj[0].keys())
        tem_id = any("id" == c or c.endswith("_id") or c.endswith("id") for c in chaves)
        tem_nome = any(c in chaves for c in ("name", "nome", "title", "description", "label"))
        if tem_id and tem_nome:
            achados.append((caminho, len(obj), sorted(chaves)))
        for it in obj[:1]:
            achar_listas_com_id_e_nome(it, f"{caminho}[]", achados)
    return achados


print("=" * 70)
print("1) GET /settings  (categorias e centros de custo com IDs)")
print("=" * 70)
status, r = tenta_get("/settings")
print(f"status: {status}")
if status == 200:
    try:
        data = r.json()
        print("\n-- estrutura (só chaves) --")
        print(json.dumps(resumo_estrutura(data), ensure_ascii=False, indent=2)[:2500])
        print("\n-- listas que parecem ser categorias/centros de custo (id + nome) --")
        for caminho, n, chaves in achar_listas_com_id_e_nome(data):
            print(f"  {caminho}: {n} itens | campos: {chaves}")

        print("\n-- categorias de SUCUMBÊNCIA (nome exato + id + tipo) --")
        cats = (data.get("financial") or {}).get("categories") or []
        for c in cats:
            if "SUCUMB" in (c.get("category") or "").upper():
                print(f"   id={c.get('id')} | tipo={c.get('type')!r} | nome={c.get('category')!r}")

        print("\n-- centros de custo (nome exato + id) --")
        for cc in ((data.get("financial") or {}).get("cost_centers") or []):
            print(f"   id={cc.get('id')} | nome={cc.get('cost_center')!r}")
    except Exception as e:
        print(f"erro ao ler JSON: {e}")
        print(r.text[:500])
else:
    print((r.text[:500]) if hasattr(r, "text") else r)

print()
print("=" * 70)
print(f"2) Caminhos candidatos de TAREFAS (processo exemplo {PROCESSO_EXEMPLO})")
print("=" * 70)
candidatos = [
    ("/posts", {"lawsuits_id": PROCESSO_EXEMPLO}),
    ("/tasks", {"lawsuits_id": PROCESSO_EXEMPLO}),
    (f"/lawsuits/{PROCESSO_EXEMPLO}/history", None),
    (f"/lawsuits/{PROCESSO_EXEMPLO}/posts", None),
    (f"/lawsuits/{PROCESSO_EXEMPLO}/tasks", None),  # o atual (esperado: 401)
]
for path, params in candidatos:
    status, r = tenta_get(path, params)
    extra = ""
    if status == 200 and hasattr(r, "json"):
        try:
            d = r.json()
            if isinstance(d, list):
                extra = f" | lista com {len(d)} itens"
                if d and isinstance(d[0], dict):
                    extra += f" | campos: {sorted(d[0].keys())}"
            elif isinstance(d, dict):
                extra = f" | chaves: {sorted(d.keys())[:15]}"
        except Exception:
            extra = " | (corpo não-JSON)"
    p = f"?{list(params.keys())}" if params else ""
    print(f"  {status}  GET {path}{p}{extra}")

print()
print("=" * 70)
print(f"3) ESTRUTURA de uma tarefa (/posts?lawsuits_id={PROCESSO_EXEMPLO})")
print("    A tarefa traz VALOR? Traz categoria/tipo? (campos sensíveis ocultos)")
print("=" * 70)
status, r = tenta_get("/posts", {"lawsuits_id": PROCESSO_EXEMPLO})
SENS = ("name", "cpf", "cnpj", "customer", "cliente", "email", "phone", "mobile", "description", "comments", "observ")
INTER = ("value", "valor", "amount", "categor", "exito", "êxito", "sucumb", "honor", "type", "tipo", "task", "title", "stage", "status")
if status == 200:
    d = r.json()
    tarefas = d.get("data", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
    print(f"status 200 | {len(tarefas)} tarefas no processo")
    if tarefas:
        print("\n-- campos de UMA tarefa --")
        for k in sorted(tarefas[0].keys()):
            v = tarefas[0][k]
            kl = k.lower()
            if any(s in kl for s in SENS):
                print(f"   {k}: [oculto]")
            elif any(s in kl for s in INTER):
                print(f"   {k}: {v!r}   <== interessa (valor/categoria/tipo)")
            else:
                print(f"   {k}: ({type(v).__name__})")
        print("\n-- resumo das tarefas: só campos de valor/categoria/tipo (texto oculto) --")
        for i, t in enumerate(tarefas[:15], 1):
            resumo = {k: t.get(k) for k in t.keys() if any(s in k.lower() for s in ("value", "valor", "amount", "categor", "exito", "sucumb", "honor", "type", "tipo", "stage", "status")) and not any(s in k.lower() for s in SENS)}
            print(f"   {i:2d}. {resumo}")
else:
    print(f"status: {status}")
    print((r.text[:400]) if hasattr(r, "text") else r)

print()
print("=" * 70)
print("4) O filtro /posts?lawsuits_id realmente filtra por processo?")
print("=" * 70)
for lid in (PROCESSO_EXEMPLO, "1", "999999999"):
    st, rr = tenta_get("/posts", {"lawsuits_id": lid})
    if st == 200 and hasattr(rr, "json"):
        d = rr.json()
        tc = d.get("totalCount") if isinstance(d, dict) else "?"
        q = d.get("query") if isinstance(d, dict) else "?"
        print(f"   lawsuits_id={lid}: totalCount={tc} | query_echo={q}")
    else:
        print(f"   lawsuits_id={lid}: status {st}")
st, rr = tenta_get("/posts", None)
if st == 200 and hasattr(rr, "json"):
    print(f"   SEM filtro: totalCount={rr.json().get('totalCount')}")

print()
print("=" * 70)
print("5) O VALOR do honorário está no objeto do processo (/lawsuits)?")
print("=" * 70)
st, rr = tenta_get(f"/lawsuits/{PROCESSO_EXEMPLO}")
if st == 200 and hasattr(rr, "json"):
    lw = rr.json()
    if isinstance(lw, dict) and lw.get("data"):
        lw = lw["data"][0] if isinstance(lw["data"], list) else lw["data"]
    SENS = ("name", "cpf", "cnpj", "customer", "cliente", "email", "phone", "mobile")
    INTER = ("value", "valor", "amount", "honor", "exito", "sucumb", "contrat", "fee", "price", "area", "type", "tipo", "subject", "assunto", "tese")
    print(f"status 200 | campos do processo:")
    if isinstance(lw, dict):
        for k in sorted(lw.keys()):
            v = lw[k]
            kl = k.lower()
            if any(s in kl for s in SENS):
                print(f"   {k}: [oculto]")
            elif any(s in kl for s in INTER):
                print(f"   {k}: {v!r}   <== interessa")
            else:
                print(f"   {k}: ({type(v).__name__})")
else:
    print(f"status: {st}")

print()
print("=" * 70)
print("6) Como filtrar as tarefas/comentários POR PROCESSO?")
print("=" * 70)
# a) testa variações do nome do parâmetro de filtro
for par in ("lawsuits_id", "lawsuit_id", "lawsuits", "id_lawsuits", "process_id"):
    st, rr = tenta_get("/posts", {par: PROCESSO_EXEMPLO})
    tc = rr.json().get("totalCount") if (st == 200 and hasattr(rr, "json") and isinstance(rr.json(), dict)) else "?"
    print(f"   filtro {par}={PROCESSO_EXEMPLO} -> totalCount={tc}")

# b) numa página de /posts, quantas tarefas têm lawsuits_id preenchido?
st, rr = tenta_get("/posts", {"limit": 200})
if st == 200 and hasattr(rr, "json"):
    itens = rr.json().get("data", [])
    com_proc = [t for t in itens if t.get("lawsuits_id")]
    print(f"\n   numa página de {len(itens)} tarefas, {len(com_proc)} têm lawsuits_id preenchido")
    # c) o texto do protocolo está em 'notes'? (procura palavras-chave, sem vazar PII)
    achou_protocolo = 0
    exemplo_campos = None
    for t in itens:
        notes = (t.get("notes") or "")
        if any(p in notes.upper() for p in ("SUCUMBENC", "ÊXITO", "EXITO", "ALVARÁ", "HONORÁRIOS")):
            achou_protocolo += 1
            if exemplo_campos is None:
                exemplo_campos = sorted(t.keys())
    print(f"   tarefas cujo 'notes' tem palavras do protocolo (sucumbencial/êxito/honorários): {achou_protocolo}")
    if exemplo_campos:
        print(f"   campos dessas tarefas: {exemplo_campos}")

print()
print("Fim do diagnóstico (nada foi lançado ou alterado).")
