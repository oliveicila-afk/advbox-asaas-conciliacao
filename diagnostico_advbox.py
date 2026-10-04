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
print("Fim do diagnóstico (nada foi lançado ou alterado).")
