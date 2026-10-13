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
CAT_NORM = {norm(k): v for k, v in CAT.items()}
# regras manuais (só no modo "um dia"): "valor=NOME DA CATEGORIA;valor=NOME..."
REGRAS_MANUAIS = {}
for par in os.environ.get("REGRAS_MANUAIS", "").split(";"):
    if "=" in par:
        a, b = par.split("=", 1)
        try: REGRAS_MANUAIS[round(float(a.strip().replace(",", ".")), 2)] = b.strip()
        except ValueError: pass
CC = {c["cost_center"]: c["id"] for c in st.get("cost_centers", [])}

TODAS = DATA.upper() == "TODAS"
GEN2 = ("HONORÁRIOS INICIAIS", "HONORÁRIOS CONTRATUAIS")
CORTE = "2026-09-01"
VALORES_PROMO = {67.0, 497.0, 597.0}   # regra definida pela Priscila -> Promoção Horizontal
CAT_PROMO = "HONORÁRIOS CONTRATUAIS INICIAIS-PROMOÇÃO HORIZONTAL"
if TODAS:
    alvos = [t for t in raw if t.get("entry_type") == "income" and t.get("category") in GEN2]
else:
    # conciliação do dia: receitas da conta ASAAS pagas na data, só com categoria genérica
    alvos = [t for t in raw if t.get("entry_type") == "income"
             and (t.get("date_payment") or "")[:10] == DATA
             and str(t.get("debit_bank") or "").upper() == "ASAAS"
             and t.get("category") in GEN2]

def tese_unica_do_cliente(t):
    cands = [x for x in raw if x.get("entry_type") == "income"
             and norm(x.get("name")) == norm(t.get("name")) and x["id"] != t["id"]
             and x.get("category") and x["category"] not in GENERICAS and "-" in x["category"]
             and x.get("cost_center")]
    teses = {x["category"] for x in cands}
    if not cands:
        return None, 0
    cands.sort(key=lambda x: x.get("date_payment") or x.get("date_due") or "", reverse=True)
    return (cands[0] if len(teses) == 1 else None), len(teses)

# --- ANÁLISE SOMENTE LEITURA dos lançamentos anteriores ao corte (sem nomes de clientes)
def analise_leitura():
    ant = [t for t in alvos if (t.get("date_payment") or t.get("date_due") or "9999")[:10] < CORTE] if TODAS else \
          [t for t in raw if t.get("entry_type") == "income" and t.get("category") in GEN2
           and (t.get("date_payment") or t.get("date_due") or "9999")[:10] < CORTE]
    # tabela valor -> tese (só lançamentos que JÁ têm tese)
    por_valor = {}
    for x in raw:
        if x.get("entry_type") == "income" and x.get("category") and x["category"] not in GENERICAS and "-" in x["category"]:
            v = round(float(x.get("amount") or 0), 2)
            por_valor.setdefault(v, {}).setdefault(x["category"], 0)
            por_valor[v][x["category"]] += 1
    dominante = {}
    for v, d in por_valor.items():
        n = sum(d.values()); top = max(d, key=d.get)
        if n >= 10 and d[top] / n >= 0.9:
            dominante[v] = top
    res = {"unica": 0, "regra_promocao": 0, "valor_dominante": 0, "ambiguo_sem_regra": 0, "sem_nada": 0}
    for t in ant:
        ref, qt = tese_unica_do_cliente(t)
        v = round(float(t.get("amount") or 0), 2)
        if ref: res["unica"] += 1
        elif v in VALORES_PROMO: res["regra_promocao"] += 1
        elif v in dominante: res["valor_dominante"] += 1
        elif qt > 1: res["ambiguo_sem_regra"] += 1
        else: res["sem_nada"] += 1
    tabela = sorted(((v, sum(d.values()), max(d, key=d.get), round(max(d.values()) / sum(d.values()), 2))
                     for v, d in por_valor.items() if sum(d.values()) >= 15), key=lambda r: -r[1])[:25]
    return {"genericos_antes_de_" + CORTE: len(ant), "como_resolver": res,
            "valores_mais_comuns(valor, qtd, tese_dominante, parcela)": tabela}

out = {"data": DATA, "dry_run": DRY, "encontrados": len(alvos), "itens": []}
MAX_PUTS = int(os.environ.get("MAX_PUTS", "60"))  # limite diário da API: 500 chamadas
puts = 0
for t in alvos:
    item = {"id": t["id"], "data": t.get("date_payment") or t.get("date_due"), "cliente": mask(t.get("name")),
            "valor": t.get("amount"), "categoria_atual": t.get("category")}
    ref, qt = tese_unica_do_cliente(t)
    v = round(float(t.get("amount") or 0), 2)
    nova = None
    if not TODAS and v in REGRAS_MANUAIS:
        nome_cat = REGRAS_MANUAIS[v]
        if norm(nome_cat) not in CAT_NORM:
            item["resultado"] = "PULADO: categoria manual ainda não aparece na API (aguarde e rode de novo)"
            out["itens"].append(item); continue
        nova = next(k for k in CAT if norm(k) == norm(nome_cat))
        item["metodo"] = "regra_manual_definida_pela_priscila"
    elif ref:
        nova, item["metodo"] = ref["category"], "tese_unica_do_cliente"
    elif v in VALORES_PROMO:
        nova, item["metodo"] = CAT_PROMO, "regra_valor_promocao_horizontal"
    else:
        item["resultado"] = ("PULADO: cliente com várias teses, sem regra" if qt > 1
                             else "PULADO: sem tese anterior e sem regra")
        out["itens"].append(item); continue
    if nova == t.get("category") or not CAT.get(nova):
        item["resultado"] = "PULADO: categoria não encontrada"
        out["itens"].append(item); continue
    item["nova_categoria"] = nova
    if DRY:
        item["resultado"] = "SIMULAÇÃO (nada alterado)"
    else:
        if puts >= MAX_PUTS:
            item["resultado"] = "PULADO (limite de alterações desta execução)"
            out["itens"].append(item); continue
        puts += 1
        r = requests.put(f"{BASE}/transactions/{t['id']}", headers=H,
                         json={"entry_type": "income", "categories_id": CAT[nova]}, timeout=30)
        time.sleep(2.2)
        item["put_status"] = r.status_code
        item["resultado"] = "ALTERADO" if r.status_code == 200 else "ERRO: " + r.text[:200]
    out["itens"].append(item)

out["resumo"] = {"alterados": sum(1 for i in out["itens"] if i.get("resultado") == "ALTERADO"),
                 "simulados": sum(1 for i in out["itens"] if str(i.get("resultado","")).startswith("SIMULA")),
                 "pulados": sum(1 for i in out["itens"] if str(i.get("resultado","")).startswith("PULADO")),
                 "erros": sum(1 for i in out["itens"] if str(i.get("resultado","")).startswith("ERRO"))}
out["analise_somente_leitura"] = analise_leitura()
json.dump(out, open("correcao_classificacao.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out["resumo"]), "de", out["encontrados"])
