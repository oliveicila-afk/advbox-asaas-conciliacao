#!/usr/bin/env python3
"""SOMENTE LEITURA. Para lançamentos de receita só com categoria genérica, descobre a tese pelo
TIPO DO PROCESSO do cliente (Advbox /lawsuits) e confere se existe categoria correspondente.
Saída: apenas totais (sem nomes, CPF ou números de processo)."""
import os, sys, json, time, unicodedata, collections, requests

TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
if not TOKEN:
    sys.exit("sem token")
B = "https://app.advbox.com.br/api/v1"
H = {"Authorization": f"Bearer {TOKEN}", "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
GEN = ("HONORÁRIOS INICIAIS", "HONORÁRIOS CONTRATUAIS")
CORTE = "2026-09-01"

def norm(n):
    n = unicodedata.normalize("NFKD", str(n or "")).encode("ascii", "ignore").decode()
    return " ".join(n.upper().split())

def get(path, **p):
    for _ in range(6):
        r = requests.get(B + path, headers=H, params=p, timeout=90)
        if r.status_code != 429:
            break
        time.sleep(30)
    time.sleep(2.2)
    return r

def paginar(path):
    out, off = [], 0
    while True:
        r = get(path, limit=1000, offset=off)
        if r.status_code != 200:
            sys.exit(f"erro {r.status_code} em {path}")
        b = r.json().get("data", [])
        out += b
        if len(b) < 1000:
            return out
        off += 1000

tx = paginar("/transactions")
ls = paginar("/lawsuits")
cats = get("/settings").json().get("financial", {}).get("categories", [])

# categorias de tese: "NATUREZA-TESE" ; índice tese -> naturezas disponíveis
tese_cat = collections.defaultdict(dict)
for c in cats:
    nome = c.get("category") or ""
    if "-" in nome and c.get("type") in ("income", "CRÉDITO"):
        nat, tese = nome.split("-", 1)
        tese_cat[norm(tese)][norm(nat)] = nome

# processo -> tipo ; cliente (por nome) -> tipos de processo (parte antes de "|")
proc_tipo = {}
cli_tipos = collections.defaultdict(set)
for l in ls:
    tipo = norm((l.get("type") or "").split("|")[0])
    if not tipo:
        continue
    proc_tipo[l.get("id")] = tipo
    for c in l.get("customers", []) or []:
        cli_tipos[norm(c.get("name"))].add(tipo)

def tipos_do_lancamento(t):
    if t.get("lawsuit_id") in proc_tipo:                 # lançamento já ligado a um processo
        return {proc_tipo[t["lawsuit_id"]]}
    return cli_tipos.get(norm(t.get("name")), set())     # senão, processos do cliente (pelo nome)

def tese_do_cliente(tipos):
    achadas = {t for t in tipos if t in tese_cat}
    if not tipos: return "sem_processo", None
    if len(achadas) == 1: return "ok", next(iter(achadas))
    if len(achadas) > 1: return "varios_processos_com_categoria", None
    return "tipo_sem_categoria", sorted(tipos)

def natureza(desc):
    d = norm(desc)
    if "EXITO" in d or "ÊXITO" in d: return "EXITO"
    if "SUCUMB" in d: return "SUCUMB"
    return "INICIAIS?"   # não dá para saber só pela descrição

def analisa(lanc):
    res = collections.Counter(); sem_cat = collections.Counter(); nat = collections.Counter()
    for t in lanc:
        status, tese = tese_do_cliente(tipos_do_lancamento(t))
        res[status] += 1
        if status == "tipo_sem_categoria":
            for x in tese: sem_cat[x] += 1
        if status == "ok":
            nat[natureza(t.get("description"))] += 1
    return {"total": len(lanc), "resultado": dict(res), "natureza_inferida_nos_resolvidos": dict(nat),
            "tipos_de_processo_sem_categoria(top15)": sem_cat.most_common(15)}

gen = [t for t in tx if t.get("entry_type") == "income" and t.get("category") in GEN]
ant = [t for t in gen if (t.get("date_payment") or t.get("date_due") or "9999")[:10] < CORTE]
dia = [t for t in gen if (t.get("date_payment") or "")[:10] == CORTE]
out = {"antes_de_2026-09-01": analisa(ant), "dia_2026-09-01": analisa(dia),
       "lawsuits_lidos": len(ls), "clientes_com_processo": len(cli_tipos), "lancamentos_ligados_a_processo": sum(1 for t in gen if t.get("lawsuit_id") in proc_tipo)}
json.dump(out, open("analise_tese_processo.json", "w"), indent=1, ensure_ascii=False)
print("ok")
