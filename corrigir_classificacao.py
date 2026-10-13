#!/usr/bin/env python3
"""Corrige lançamentos criados pela automação com classificação genérica
(categoria 'HONORÁRIOS INICIAIS' + centro 'DESPESAS FINANCEIRAS-GERAL'),
trocando pela tese do cliente (categoria e centro de custo do lançamento anterior
do mesmo cliente). Não apaga nada. Roda só no GitHub Actions."""
import os, sys, json, time, unicodedata, requests

TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
DATA = os.environ.get("TARGET_DATE", "").strip()
DRY = os.environ.get("DRY_RUN", "true").lower() in ("true", "1", "yes")
if not TOKEN or not DATA:
    sys.exit("faltam ADVBOX_TOKEN/TARGET_DATE")

BASE = "https://app.advbox.com.br/api/v1"
H = {"Authorization": f"Bearer {TOKEN}", "User-Agent": "Mozilla/5.0",
     "Accept": "application/json", "Content-Type": "application/json"}
GENERICAS = {"HONORÁRIOS INICIAIS", "HONORÁRIOS FINAIS", "HONORÁRIOS DE SUCUMBÊNCIA", "HONORÁRIOS POR MENSALIDADE"}

def norm(n):
    n = unicodedata.normalize("NFKD", str(n or "")).encode("ascii", "ignore").decode()
    return " ".join(n.upper().split())

def mask(n):
    p = (n or "").split()
    return (p[0].title() + "".join(f" {x[0].upper()}." for x in p[1:])) if p else "(sem nome)"

def get(path, **params):
    for _ in range(6):
        r = requests.get(f"{BASE}{path}", headers=H, params=params, timeout=60)
        if r.status_code != 429:
            break
        time.sleep(30)
    time.sleep(2.2)
    return r

raw, off = [], 0
while True:
    r = get("/transactions", limit=1000, offset=off)
    if r.status_code != 200:
        sys.exit(f"erro {r.status_code} lendo lançamentos")
    b = r.json().get("data", [])
    raw += b
    if len(b) < 1000:
        break
    off += 1000

st = get("/settings").json().get("financial", {})
CAT = {c["category"]: c["id"] for c in st.get("categories", [])}
CC = {c["cost_center"]: c["id"] for c in st.get("cost_centers", [])}

alvos = [t for t in raw if t.get("entry_type") == "income"
         and (t.get("date_payment") or "")[:10] == DATA
         and str(t.get("debit_bank") or "").upper() == "ASAAS"
         and t.get("category") == "HONORÁRIOS INICIAIS"
         and t.get("cost_center") == "DESPESAS FINANCEIRAS-GERAL"]

out = {"data": DATA, "dry_run": DRY, "encontrados": len(alvos), "itens": []}
for t in alvos:
    item = {"id": t["id"], "cliente": mask(t.get("name")), "valor": t.get("amount")}
    cands = [x for x in raw if x.get("entry_type") == "income"
             and norm(x.get("name")) == norm(t.get("name")) and x["id"] != t["id"]
             and x.get("category") and x["category"] not in GENERICAS and "-" in x["category"]
             and x.get("cost_center")]
    if not cands:
        item["resultado"] = "SEM_PRECEDENTE (informar a tese)"
        out["itens"].append(item); continue
    cands.sort(key=lambda x: x.get("date_payment") or x.get("date_due") or "", reverse=True)
    ref = cands[0]
    item["nova_categoria"] = ref["category"]; item["novo_centro_custo"] = ref["cost_center"]
    if DRY:
        item["resultado"] = "SIMULAÇÃO (nada alterado)"
    else:
        body = {"entry_type": "income", "categories_id": CAT.get(ref["category"]),
                "cost_centers_id": CC.get(ref["cost_center"])}
        r = requests.put(f"{BASE}/transactions/{t['id']}", headers=H, json=body, timeout=30)
        time.sleep(2.2)
        item["put_status"] = r.status_code
        item["put_resposta"] = r.text[:300]
        g = get(f"/transactions/{t['id']}")
        d = g.json() if g.status_code == 200 else {}
        d = d.get("data", d) if isinstance(d, dict) else {}
        item["depois_categoria"] = d.get("category")
        item["depois_centro_custo"] = d.get("cost_center")
    out["itens"].append(item)

json.dump(out, open("correcao_classificacao.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
