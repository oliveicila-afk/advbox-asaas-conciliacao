#!/usr/bin/env python3
"""
Conciliação Diária — Asaas vs Advbox
Busca TODAS as receitas recebidas em uma data, compara e CORRIGE divergências.
COM LOGGING MASSIVO EM ARQUIVO PARA DEBUG
"""

import os
import requests
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import time
import re

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "").strip()
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
TARGET_DATE  = os.environ.get("TARGET_DATE", "2026-09-01").strip()
TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")

ASAAS_INCOME_TYPES = ["PAYMENT_RECEIVED", "RECEIVABLE_ANTICIPATION_GROSS_CREDIT", "PAYMENT_FEE_REVERSAL"]
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ["true", "1", "yes"]

MAX_RECONCILIATION_ATTEMPTS = 5
TOLERANCE = 0.01

CATEGORIAS_HONORARIOS_INICIAIS = [1]      # HONORÁRIOS INICIAIS (ID real no Advbox)
CATEGORIAS_HONORARIOS_EXITO = [2]         # HONORÁRIOS FINAIS
CATEGORIAS_HONORARIOS_INCUMBENCIAL = [3]  # HONORÁRIOS DE SUCUMBÊNCIA
COST_CENTER_ASAAS_PADRAO = 60814

# Transações de investimento: excluídas da conciliação (já lançadas na conta de investimentos do Advbox)
NOMES_INVESTIMENTO = ("LVMX", "FII ", "FIDC", "FUNDO DE INVESTIMENTO", "FUNDO IMOBILIARIO",
                      "FI MULTIMERCADO", "FI RENDA FIXA", "INVESTIMENTOS", "ASSET MANAGEMENT")

# CNPJs de entidades financeiras/investimento que devem ser excluídas da conciliação
CNPJS_INVESTIMENTO: tuple = ()  # adicionar CNPJs conforme identificado

# LOGGING EM ARQUIVO
LOG_FILE = f"debug_{TARGET_DATE}.log"
def log_msg(msg, print_also=True):
    """Escreve em arquivo de log E opcionalmente na tela"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    if print_also:
        print(msg)

# Inicia log
open(LOG_FILE, "w").close()  # Limpa arquivo anterior
log_msg(f"{'='*100}\nINÍCIO DO LOG DE DEBUG\nData/Hora: {datetime.now()}\nTarget Date: {TARGET_DATE}\nDRY_RUN: {DRY_RUN}\n{'='*100}", True)

# Valida tokens
log_msg(f"\n[VALIDAÇÃO] ASAAS_TOKEN definido: {bool(ASAAS_TOKEN)}", True)
log_msg(f"[VALIDAÇÃO] ADVBOX_TOKEN definido: {bool(ADVBOX_TOKEN)}", True)

# ---------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------------------------
def inferir_categoria(description: str) -> int:
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in ["êxito", "sucesso"]):
        return CATEGORIAS_HONORARIOS_EXITO[0]
    elif any(kw in desc_lower for kw in ["inicial", "protocolo", "entrada"]):
        return CATEGORIAS_HONORARIOS_INICIAIS[0]
    elif any(kw in desc_lower for kw in ["incumbencial", "mensal", "recursal"]):
        return CATEGORIAS_HONORARIOS_INCUMBENCIAL[0]
    return CATEGORIAS_HONORARIOS_INICIAIS[0]


def delete_advbox_transaction(tx_id: str, headers_advbox: dict) -> bool:
    try:
        resp = requests.delete(
            f"https://app.advbox.com.br/api/v1/transactions/{tx_id}",
            headers=headers_advbox,
            timeout=30
        )
        success = resp.status_code in [200, 204]
        log_msg(f"  DELETE {tx_id}: {resp.status_code} - {'✓' if success else '❌'}", True)
        return success
    except Exception as e:
        log_msg(f"  ❌ Erro ao deletar {tx_id}: {e}", True)
        return False


def unpay_advbox_transaction(tx_id, headers_advbox: dict) -> bool:
    """Desmarca o pagamento (volta para "não pago") em vez de apagar. Reversível.
    API Advbox: PUT /transactions/{id} com {"date_payment": ""} (null é recusado, testado)."""
    try:
        resp = requests.put(
            f"https://app.advbox.com.br/api/v1/transactions/{tx_id}",
            headers={**headers_advbox, "Content-Type": "application/json"},
            json={"date_payment": ""},
            timeout=30
        )
        success = resp.status_code in [200, 204]
        log_msg(f"  DESMARCAR PAGAMENTO {tx_id}: {resp.status_code} - {'✓' if success else '❌ ' + resp.text[:300]}", True)
        return success
    except Exception as e:
        log_msg(f"  ❌ Erro ao desmarcar pagamento {tx_id}: {e}", True)
        return False



GENERICAS = {"HONORÁRIOS INICIAIS", "HONORÁRIOS FINAIS", "HONORÁRIOS DE SUCUMBÊNCIA", "HONORÁRIOS POR MENSALIDADE"}

def carregar_settings_advbox(headers_advbox):
    """IDs de categorias e centros de custo (nome -> id). 1 chamada, guardada."""
    if _SETTINGS:
        return _SETTINGS
    r = requests.get("https://app.advbox.com.br/api/v1/settings", headers=headers_advbox, timeout=30)
    time.sleep(2.2)
    f = r.json().get("financial", {}) if r.status_code == 200 else {}
    _SETTINGS["cat"] = {c["category"]: c["id"] for c in f.get("categories", [])}
    _SETTINGS["cc"] = {c["cost_center"]: c["id"] for c in f.get("cost_centers", [])}
    return _SETTINGS

def classificacao_por_precedente(nome, headers_advbox):
    """Tese do cliente = categoria e centro de custo do lançamento anterior mais recente
    do MESMO cliente (receita com categoria da tese, não a genérica)."""
    alvo = norm_nome(nome)
    if not alvo:
        return None
    cands = [t for t in _ADVBOX_RAW
             if t.get("entry_type") == "income"
             and norm_nome(t.get("name")) == alvo
             and t.get("category") and t["category"] not in GENERICAS and ("-" in t["category"] or t["category"].startswith("HONORÁRIOS CONSULTORIAS"))
             and t.get("cost_center")]
    if not cands:
        return None
    cands.sort(key=lambda t: t.get("date_payment") or t.get("date_due") or "", reverse=True)
    ref = cands[0]
    st = carregar_settings_advbox(headers_advbox)
    cat_id = st["cat"].get(ref["category"])
    cc_id = st["cc"].get(ref["cost_center"])
    if not cat_id or not cc_id:
        return None
    nova = aplicar_regra_consultoria(ref["category"], ref["cost_center"], headers_advbox)
    if nova:
        return {"categories_id": nova[1], "cost_centers_id": cc_id,
                "categoria": nova[0], "centro_custo": ref["cost_center"]}
    return {"categories_id": cat_id, "cost_centers_id": cc_id,
            "categoria": ref["category"], "centro_custo": ref["cost_center"]}


def _so_alnum(n):
    return re.sub(r"[^A-Z0-9]", "", norm_nome(n))

def categoria_promocao_horizontal(headers_advbox):
    """Única categoria de Promoção Horizontal que não é de êxito (regra 67/497/597)."""
    st = carregar_settings_advbox(headers_advbox)
    cats = [(n, i) for n, i in st["cat"].items() if _sem_acento(n).endswith("INICIAIS-PROMOCAO HORIZONTAL")]
    return cats[0] if len(cats) == 1 else None

CAT_CONSULTORIA_ANTIGA = "HONORÁRIOS CONSULTORIAS"
CAT_CONSULTORIA_CLIENTE = "HONORÁRIOS CONTRATUAIS INICIAIS-CONSULTORIA"
CENTROS_SEM_AJUSTE_CONSULTORIA = ("PARCERIAS", "GERAL")

def categoria_consultoria_cliente(headers_advbox):
    """Regra do escritório (ensinada na tela do Advbox): consultoria de CLIENTE usa a categoria
    'HONORÁRIOS CONTRATUAIS INICIAIS-CONSULTORIA', e não 'HONORÁRIOS CONSULTORIAS'.
    Parceria (centro de custo PARCERIAS) e centro GERAL ficam como estão."""
    st = carregar_settings_advbox(headers_advbox)
    alvo = _sem_acento(CAT_CONSULTORIA_CLIENTE)
    ach = [(n, i) for n, i in st["cat"].items() if _sem_acento(n).endswith(alvo)]
    return ach[0] if len(ach) == 1 else None

def aplicar_regra_consultoria(categoria, centro, headers_advbox):
    """Devolve (nome, id) da categoria correta se a regra se aplica; senão None."""
    if _sem_acento(categoria) != _sem_acento(CAT_CONSULTORIA_ANTIGA):
        return None
    if _sem_acento(centro) in CENTROS_SEM_AJUSTE_CONSULTORIA:
        return None
    return categoria_consultoria_cliente(headers_advbox)


def categoria_iniciais_da_tese(tipo, headers_advbox):
    """Categoria 'HONORÁRIOS CONTRATUAIS INICIAIS-<TESE>' pelo tipo do processo (regra: lançamento só 'Honorários Contratuais' é genérico e deve ir para iniciais + tese).
    Anulação de Questão -> CONCURSO PM/AM ITEM B; FIC -> CONCURSO. Sem categoria para a tese -> None (fica pendente)."""
    st = carregar_settings_advbox(headers_advbox)
    pref = "HONORARIOS CONTRATUAIS INICIAIS-"
    ini = {n: i for n, i in st["cat"].items() if _sem_acento(n).startswith(pref)}
    t = _sem_acento(tipo)
    if not t:
        return None
    if "ANULACAO DE QUESTAO" in t:
        alvo = pref + "CONCURSO PM/AM ITEM B"
    elif t == "FIC" or t.startswith("FIC "):
        alvo = pref + "CONCURSO"
    else:
        ex = [(n, i) for n, i in ini.items() if _sem_acento(n) == pref + t]
        if len(ex) == 1:
            return ex[0]
        c = [(n, i) for n, i in ini.items() if _sem_acento(n)[len(pref):] and _sem_acento(n)[len(pref):] in t]
        if not c:
            return None
        m = max(len(_sem_acento(n)) for n, _ in c)
        c = [(n, i) for n, i in c if len(_sem_acento(n)) == m]
        return c[0] if len(c) == 1 else None
    ex = [(n, i) for n, i in ini.items() if _sem_acento(n) == alvo]
    return ex[0] if len(ex) == 1 else None


def pagar_lancamento_existente(tx_id, data_pag, valor, headers_advbox):
    """Define a data de pagamento de um lançamento que JÁ existe. A API exige o payload completo
    (entry_type, conta ASAAS, categoria, centro de custo, cliente, processo). Se a categoria gravada
    não existe mais (422 em categories_id) e o valor é 67/497/597, troca pela categoria de Promoção Horizontal."""
    u = f"https://app.advbox.com.br/api/v1/transactions/{tx_id}"
    hj = {**headers_advbox, "Content-Type": "application/json"}
    d = requests.get(u, headers=headers_advbox, timeout=30).json()
    time.sleep(2.2)
    p = {"entry_type": d.get("entry_type") or "income", "users_id": d.get("users_id") or 65747, "debit_account": 193264,
         "categories_id": d.get("categories_id"), "cost_centers_id": d.get("cost_centers_id"),
         "customers_id": d.get("customers_id"), "lawsuits_id": d.get("lawsuits_id"),
         "amount": f"{float(d.get('amount', valor)):.2f}".replace(".", ","),
         "date_due": str(d.get("date_due"))[:10], "date_payment": data_pag, "description": d.get("description") or ""}
    st_ = carregar_settings_advbox(headers_advbox)
    if d.get("categories_id") not in st_["cat"].values():
        # categoria gravada genérica/antiga ("Honorários Contratuais"): troca por INICIAIS-<tese do processo>
        lw_ = next((l for l in indice_processos(headers_advbox).values() if l.get("id") == d.get("lawsuits_id")), None)
        tipo_ = (lw_ or {}).get("type")
        tipo_ = tipo_.get("name") if isinstance(tipo_, dict) else tipo_
        ci = categoria_iniciais_da_tese(tipo_, headers_advbox)
        if ci:
            log_msg(f"  categoria genérica -> '{ci[0]}'", True)
            p["categories_id"] = ci[1]
        else:
            log_msg("  ⚠️ categoria genérica sem categoria de iniciais para a tese - fica pendente", True)
            pendentes_sem_tese.append({"valor": round(float(valor), 2), "cliente_asaas": "(lançamento %s)" % tx_id,
                                       "motivo": "categoria genérica e tese sem categoria de iniciais"})
    nova = aplicar_regra_consultoria(d.get("category"), d.get("cost_center"), headers_advbox)
    if nova:
        log_msg(f"  consultoria de cliente -> categoria '{nova[0]}'", True)
        p["categories_id"] = nova[1]
    p = {k: v for k, v in p.items() if v is not None}
    rr = requests.put(u, headers=hj, json=p, timeout=30)
    time.sleep(2.2)
    if rr.status_code == 422 and "categories_id" in rr.text and round(float(valor), 2) in (67.0, 497.0, 597.0):
        ph = categoria_promocao_horizontal(headers_advbox)
        if ph:
            log_msg(f"  categoria antiga inválida -> usando '{ph[0]}' (regra 67/497/597)", True)
            p["categories_id"] = ph[1]
            rr = requests.put(u, headers=hj, json=p, timeout=30)
            time.sleep(2.2)
    return rr.status_code in (200, 204)


def _sem_acento(t):
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().upper().strip()

def origem_do_cliente(customers_id, headers_advbox):
    """Origem do cliente = campo 'origem' do menu PESSOAS do Advbox (regra do escritório para o centro de custo)."""
    try:
        r = requests.get(f"https://app.advbox.com.br/api/v1/customers/{customers_id}", headers=headers_advbox, timeout=30)
        time.sleep(2.2)
        d = r.json() if r.status_code == 200 else {}
        o = d.get("origin")
        return (o.get("name") if isinstance(o, dict) else o) or ""
    except Exception:
        return ""

def centro_custo_por_tese(tipo, categoria, headers_advbox):
    """Regras do escritório (combinadas na conversa) para centro de custo pela TESE, quando a origem não resolve:
    concurso / item B / anulação de questão -> CONCURSO-TRÁFEGO PAGO; pedagogo e terço de férias -> PROFESSOR/PEDAGOGO-TRÁFEGO PAGO;
    defesa PAD (servidor) -> SERVIDOR PUBLICO-TRÁFEGO PAGO; parceria -> PARCERIAS; demanda civil -> OUTROS-TRÁFEGO PAGO;
    retroativo de promoção (vertical/horizontal), abono permanência e revisão de aposentadoria -> PROFESSOR/PEDAGOGO-TRÁFEGO PAGO;
    planejamento previdenciário -> SERVIDOR PUBLICO-TRÁFEGO PAGO."""
    t = _sem_acento((tipo or "") + " " + ((categoria or "").split("-", 1)[1] if "-" in (categoria or "") else ""))
    if "PARCERIA" in t:
        alvo = "PARCERIAS"
    elif "CONCURSO" in t or "ITEM B" in t or "ANULACAO DE QUESTAO" in t:
        alvo = "CONCURSO-TRAFEGO PAGO"
    elif "PEDAGOGO" in t or "FERIAS" in t:
        alvo = "PROFESSOR/PEDAGOGO-TRAFEGO PAGO"
    elif "DEFESA PAD" in t or t.startswith("PAD ") or "PROCESSO ADMINISTRATIVO DISCIPLINAR" in t:
        alvo = "SERVIDOR PUBLICO-TRAFEGO PAGO"
    elif "DEMANDA CIVIL" in t:
        alvo = "OUTROS-TRÁFEGO PAGO"
    elif "PLANEJAMENTO PREVIDENCIARIO" in t:
        alvo = "SERVIDOR PUBLICO-TRAFEGO PAGO"
    elif ("RETROATIVO" in t and "PROMOCAO" in t) or "ABONO PERMANENCIA" in t or "REVISAO DE APOSENTADORIA" in t:
        alvo = "PROFESSOR/PEDAGOGO-TRAFEGO PAGO"
    else:
        return None
    st = carregar_settings_advbox(headers_advbox)
    ach = [(n, i) for n, i in st["cc"].items() if _sem_acento(n) == alvo]
    return ach[0] if len(ach) == 1 else None


def centro_custo_por_origem(origem, grupo, tipo, headers_advbox):
    """Centro de custo = <PROFISSÃO/ÁREA>-<CANAL>.
    CANAL vem da ORIGEM do cliente (menu Pessoas); ÁREA vem da profissão escrita na origem ou, se não houver,
    do grupo/tese do processo. O nome precisa existir no Advbox; se não existir ou for ambíguo, devolve None (fica pendente)."""
    o, g, t = _sem_acento(origem), _sem_acento(grupo), _sem_acento(tipo)
    if o == "ESCRITORIO":
        st0 = carregar_settings_advbox(headers_advbox)
        ach0 = [(n, i) for n, i in st0["cc"].items() if _sem_acento(n) == "ESCRITORIO-INDICACAO"]
        return ach0[0] if len(ach0) == 1 else None
    if "TRAFEGO" in o or "ANUNCIO" in o or "FACEBOOK" in o or "GOOGLE" in o:
        canal = "TRAFEGO PAGO"
    elif "INDICACAO" in o:
        canal = "INDICACAO"
    elif "ORGANICO" in o or "SITE DO ESCRITORIO" in o:
        canal = "ORGANICO"
    elif "PROSPECCAO" in o:
        canal = "PROSPECCAO ATIVA"
    elif "INSTAGRAM" in o:
        canal = "INSTAGRAM / MIDIA SOCIAL"
    else:
        return None
    if "PROFESSOR" in o or "PEDAGOGO" in o:
        area = "PROFESSOR/PEDAGOGO"
    elif any(k in o for k in ("GRUPO DE APOIO", "MERENDEIRA", "VIGIA", "ASSISTENTE", "AUXILIAR DE SERVICOS")):
        area = "GRUPO DE APOIO"
    elif "SOLDADO" in o or "ANULACAO DE QUESTAO" in t or "PM/AM" in t:
        area = "PM/AM"
    elif "CONSUMIDOR" in g:
        area = "CONSUMIDOR"
    elif "CONCURSO" in g:
        area = "CONCURSO"
    elif "SERVIDOR" in g:
        area = "SERVIDOR PUBLICO"
    else:
        return None
    st = carregar_settings_advbox(headers_advbox)
    alvo = f"{area}-{canal}"
    achados = [(n, i) for n, i in st["cc"].items() if _sem_acento(n) == alvo]
    return achados[0] if len(achados) == 1 else None

def categoria_exito_da_tese(tipo, headers_advbox):
    """Categoria 'HONORÁRIOS CONTRATUAIS DE ÊXITO-<TESE>' pelo tipo do processo. Anulação de Questão -> CONCURSO PM/AM ITEM B; FIC -> CONCURSO."""
    st = carregar_settings_advbox(headers_advbox)
    t = _sem_acento(tipo)
    pref = "HONORARIOS CONTRATUAIS DE EXITO-"
    cats = {n: i for n, i in st["cat"].items() if _sem_acento(n).startswith(pref)}
    if "ANULACAO DE QUESTAO" in t:
        alvo = pref + "CONCURSO PM/AM ITEM B"
    elif t == "FIC" or t.startswith("FIC "):
        alvo = pref + "CONCURSO"
    else:
        cand = [(n, i) for n, i in cats.items() if _sem_acento(n)[len(pref):] and _sem_acento(n)[len(pref):] in t]
        if not cand:
            return None
        maior = max(len(_sem_acento(n)) for n, _ in cand)
        cand = [(n, i) for n, i in cand if len(_sem_acento(n)) == maior]
        return cand[0] if len(cand) == 1 else None
    for n, i in cats.items():
        if _sem_acento(n) == alvo:
            return (n, i)
    return None

def classificacao_por_processo_e_origem(customers_id, headers_advbox):
    """Cliente sem lançamento anterior: tese pelo ÚNICO processo dele no Advbox e centro de custo pela ORIGEM (menu Pessoas)."""
    idx = indice_processos(headers_advbox)
    vistos, procs = set(), []
    for l in idx.values():
        if l.get("id") in vistos:
            continue
        vistos.add(l.get("id"))
        if any(isinstance(c, dict) and c.get("customer_id") == customers_id for c in (l.get("customers") or [])):
            procs.append(l)
    teses = {}
    for l in procs:
        tipo = l.get("type", {}).get("name") if isinstance(l.get("type"), dict) else l.get("type")
        grupo = l.get("group", {}).get("name") if isinstance(l.get("group"), dict) else l.get("group")
        cat = categoria_exito_da_tese(tipo, headers_advbox)
        if cat:
            teses[cat[0]] = (cat, l, tipo, grupo)
    if len(teses) != 1:
        return None
    cat, l, tipo, grupo = list(teses.values())[0]
    origem = origem_do_cliente(customers_id, headers_advbox)
    if not origem:
        for c in l.get("customers") or []:
            if isinstance(c, dict) and c.get("customer_id") == customers_id:
                origem = c.get("origin") or ""
    cc = centro_custo_por_origem(origem, grupo, tipo, headers_advbox) or centro_custo_por_tese(tipo, cat[0], headers_advbox)
    if not cc:
        return None
    return {"categories_id": cat[1], "cost_centers_id": cc[1], "categoria": cat[0],
            "centro_custo": f"{cc[0]} (origem: {origem})", "lawsuits_id": l.get("id")}


def indice_processos(headers_advbox):
    """Índice {20 dígitos do processo: processo Advbox} (lido uma vez, respeitando o limite da API)."""
    global _LAWSUIT_IDX
    if _LAWSUIT_IDX is not None:
        return _LAWSUIT_IDX
    idx, off = {}, 0
    while True:
        r = None
        for _ in range(6):
            r = requests.get("https://app.advbox.com.br/api/v1/lawsuits", headers=headers_advbox,
                             params={"limit": 1000, "offset": off}, timeout=90)
            if r.status_code != 429:
                break
            time.sleep(30)
        time.sleep(2.2)
        if r.status_code != 200:
            log_msg(f"  ⚠️ lawsuits HTTP {r.status_code}", True)
            break
        b = r.json().get("data", [])
        for l in b:
            for k in ("process_number", "protocol_number"):
                d = re.sub(r"\D", "", str(l.get(k) or ""))
                if len(d) == 20:
                    idx[d] = l
        if len(b) < 1000:
            break
        off += 1000
    _LAWSUIT_IDX = idx
    return idx


def processo_do_repasse(a_tx, headers_advbox):
    """Acha o processo no Advbox pelo número que vem na cobrança do Asaas (testa toda janela de 20 dígitos)."""
    idx = indice_processos(headers_advbox)
    for ds in a_tx.get("_proc_longas") or []:
        for off in range(0, len(ds) - 19):
            if ds[off:off + 20] in idx:
                return idx[ds[off:off + 20]]
    return None


def detalhe_lancamento(tx_id, headers_advbox):
    r = requests.get(f"https://app.advbox.com.br/api/v1/transactions/{tx_id}", headers=headers_advbox, timeout=30)
    time.sleep(2.2)
    return r.json() if r.status_code == 200 else {}


def lancar_receita_exito_caixa(plano, headers_advbox):
    """Cria a receita CHEIA do repasse (categoria, centro de custo, cliente e processo copiados dos honorários
    já lançados) e desmarca só o lançamento de honorários antigo. A despesa 'ÊXITO DO CLIENTE' é mantida."""
    a_tx, fee_tx, lei, v = plano
    d = detalhe_lancamento(fee_tx.get("id"), headers_advbox)
    if not (d.get("categories_id") and d.get("cost_centers_id") and d.get("customers_id")):
        log_msg(f"  Caixa R${v}: modelo sem categoria/centro/cliente - NÃO lançado", True)
        return False
    payload = {"users_id": 65747, "entry_type": "income", "debit_account": 193264,
               "categories_id": d["categories_id"], "cost_centers_id": d["cost_centers_id"],
               "customers_id": d["customers_id"], "lawsuits_id": lei.get("id"),
               "amount": f"{v:.2f}".replace(".", ","), "date_due": TARGET_DATE, "date_payment": TARGET_DATE,
               "description": f"Repasse Caixa (êxito) - fatura {a_tx.get('_fatura_nr')}"}
    r = requests.post("https://app.advbox.com.br/api/v1/transactions",
                      headers={**headers_advbox, "Content-Type": "application/json"}, json=payload, timeout=30)
    ok = r.status_code in (200, 201)
    log_msg(f"  CREATE receita Caixa R${v}: {r.status_code} - {'✓' if ok else '❌ ' + r.text[:200]}", True)
    if ok:
        unpay_advbox_transaction(fee_tx.get("id"), headers_advbox)
    return ok

def buscar_cliente_advbox(asaas_tx: dict, headers_advbox: dict):
    """Acha o cliente no Advbox pelo CPF/CNPJ (preferido) ou pelo nome exato."""
    try:
        base = "https://app.advbox.com.br/api/v1/customers"
        cpf = "".join(ch for ch in str(asaas_tx.get("_cpf") or "") if ch.isdigit())
        if cpf:
            r = requests.get(base, headers=headers_advbox, params={"identification": cpf, "limit": 5}, timeout=30)
            time.sleep(2.2)
            dados = (r.json().get("data") or []) if r.status_code == 200 else []
            if dados:
                return dados[0].get("id")
        nome = norm_nome(asaas_tx.get("_nome"))
        if nome:
            r = requests.get(base, headers=headers_advbox, params={"name": asaas_tx.get("_nome"), "limit": 20}, timeout=30)
            time.sleep(2.2)
            for c in (r.json().get("data") or []) if r.status_code == 200 else []:
                if norm_nome(c.get("name")) == nome:
                    return c.get("id")
    except Exception as e:
        log_msg(f"  ⚠️ busca de cliente falhou: {type(e).__name__}", False)
    return None


def create_advbox_transaction(asaas_tx: dict, headers_advbox: dict) -> bool:
    """Cria a receita já paga na conta ASAAS, ligada ao cliente (nome vem do cliente)."""
    try:
        # Pagador PESSOA JURÍDICA (CNPJ) via TED/Pix sem processo: precisa de identificação manual do cliente/tese
        doc = "".join(ch for ch in str(asaas_tx.get("_cpf") or "") if ch.isdigit())
        if len(doc) == 14:
            log_msg(f"  CREATE: pagador CNPJ '{mascara_nome(asaas_tx.get('_nome'))}' R${float(asaas_tx.get('value', 0)):.2f} - NÃO criado (identificar cliente/tese manualmente)", True)
            pendentes_sem_tese.append({"valor": round(float(asaas_tx.get("value", 0)), 2),
                                       "cliente_asaas": mascara_nome(asaas_tx.get("_nome")), "motivo": "pagador CNPJ sem processo"})
            return False
        customers_id = buscar_cliente_advbox(asaas_tx, headers_advbox)
        if not customers_id:
            log_msg(f"  CREATE: cliente '{mascara_nome(asaas_tx.get('_nome'))}' não encontrado no Advbox - NÃO criado (precisa cadastrar o cliente)", True)
            return False
        description = asaas_tx.get("description") or "Pagamento Asaas"
        classif = classificacao_por_precedente(asaas_tx.get("_nome"), headers_advbox)
        if not classif:
            # Sem lançamento pago anterior: copia categoria e centro de custo do lançamento PREVISTO (em aberto) do mesmo cliente
            alvo_n = norm_nome(asaas_tx.get("_nome"))
            prev = [t for t in _ADVBOX_RAW if t.get("entry_type") == "income" and not t.get("date_payment")
                    and norm_nome(t.get("name")) == alvo_n and t.get("category") and t["category"] not in GENERICAS
                    and "-" in t["category"] and t.get("cost_center")]
            prev.sort(key=lambda t: str(t.get("date_due") or ""))
            if prev:
                st = carregar_settings_advbox(headers_advbox)
                ci, ccid = st["cat"].get(prev[0]["category"]), st["cc"].get(prev[0]["cost_center"])
                if ci and ccid:
                    classif = {"categories_id": ci, "cost_centers_id": ccid,
                               "categoria": prev[0]["category"], "centro_custo": prev[0]["cost_center"]}
                    nova = aplicar_regra_consultoria(prev[0]["category"], prev[0]["cost_center"], headers_advbox)
                    if nova:
                        classif.update({"categories_id": nova[1], "categoria": nova[0]})
        if not classif and round(float(asaas_tx.get("value", 0)), 2) in (67.0, 497.0, 597.0):
            # regra combinada: valores 67/497/597 podem ser Promoção Horizontal
            ph = categoria_promocao_horizontal(headers_advbox)
            if ph:
                classif = {"categories_id": ph[1], "cost_centers_id": COST_CENTER_ASAAS_PADRAO,
                           "categoria": ph[0], "centro_custo": "padrão ASAAS"}
        if not classif:
            classif = classificacao_por_processo_e_origem(customers_id, headers_advbox)
        if not classif:
            log_msg(f"  CREATE: cliente '{mascara_nome(asaas_tx.get('_nome'))}' sem lançamento anterior com tese - NÃO criado (informar a tese)", True)
            pendentes_sem_tese.append({"valor": round(float(asaas_tx.get("value", 0)), 2),
                                       "cliente_asaas": mascara_nome(asaas_tx.get("_nome"))})
            return False
        log_msg(f"  Tese pelo precedente: {classif['categoria']} | {classif['centro_custo']}", True)
        payload = {
            "users_id": 65747,
            "entry_type": "income",
            "debit_account": 193264,
            "categories_id": classif["categories_id"],
            "cost_centers_id": classif["cost_centers_id"],
            "amount": f"{float(asaas_tx.get('value', 0)):.2f}".replace(".", ","),
            "date_due": TARGET_DATE,
            "date_payment": TARGET_DATE,
            "customers_id": customers_id,
            "description": description,
        }
        if classif.get("lawsuits_id"):
            payload["lawsuits_id"] = classif["lawsuits_id"]
        resp = requests.post(
            "https://app.advbox.com.br/api/v1/transactions",
            headers={**headers_advbox, "Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        success = resp.status_code in [200, 201]
        log_msg(f"  CREATE: {resp.status_code} - {'✓' if success else '❌ ' + resp.text[:300]}", True)
        return success
    except Exception as e:
        log_msg(f"  ❌ Erro ao criar: {e}", True)
        return False



import unicodedata

def norm_nome(n):
    if not n:
        return ""
    n = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode()
    return " ".join(n.upper().split())

def mascara_nome(n):
    partes = (n or "").split()
    if not partes:
        return "(sem nome)"
    return partes[0].title() + "".join(f" {p[0].upper()}." for p in partes[1:])

_CACHE_PAG = {}
_CACHE_CLI = {}

def asaas_nome(tx, headers):
    """Nome do cliente no Asaas: lançamento -> cobrança (paymentId) -> cliente.
    Antecipações: anticipationId -> cobrança -> cliente."""
    try:
        base = "https://api.asaas.com/v3"
        pid = tx.get("paymentId")
        if not pid and tx.get("anticipationId"):
            a = requests.get(f"{base}/anticipations/{tx['anticipationId']}", headers=headers, timeout=30).json()
            pid = a.get("payment")
        if not pid:
            return None
        if pid not in _CACHE_PAG:
            pj = requests.get(f"{base}/payments/{pid}", headers=headers, timeout=30).json()
            _CACHE_PAG[pid] = pj.get("customer")
            _CACHE_PROC[pid] = [re.sub(r"\D", "", x) for x in re.findall(r"\d[\d\-\.\/]{18,}\d",
                                f"{pj.get('description') or ''} | {pj.get('externalReference') or ''}")]
            _CACHE_FAT[pid] = pj.get("invoiceNumber")
        tx["_proc_longas"] = _CACHE_PROC.get(pid, [])
        tx["_fatura_nr"] = _CACHE_FAT.get(pid)
        cid = _CACHE_PAG[pid]
        if not cid:
            return None
        if cid not in _CACHE_CLI:
            _CACHE_CLI[cid] = requests.get(f"{base}/customers/{cid}", headers=headers, timeout=30).json()
        tx["_cpf"] = (_CACHE_CLI[cid] or {}).get("cpfCnpj")
        return (_CACHE_CLI[cid] or {}).get("name")
    except Exception as e:
        log_msg(f"  ⚠️ nome Asaas não resolvido: {type(e).__name__}", False)
        return None

# ---------------------------------------------------------------------------
# FUNÇÕES DE LEITURA COM LOGGING MASSIVO
# ---------------------------------------------------------------------------
def fetch_asaas_transactions():
    """Busca Asaas com logging COMPLETO"""
    transactions = []
    headers_asaas = {
        "access_token": ASAAS_TOKEN,
        "Accept": "application/json"
    }

    log_msg(f"\n[ASAAS] Iniciando fetch", True)

    # Mesmo critério do workflow consultar-total-asaas: sem filtro "type" na API
    # (ele não filtra e duplicava os dados); filtra o tipo aqui e remove duplicados.
    all_raw = []
    offset = 0
    limit = 100
    while True:
        try:
            params = {"startDate": TARGET_DATE, "finishDate": TARGET_DATE, "limit": limit, "offset": offset}
            resp = requests.get("https://api.asaas.com/v3/financialTransactions",
                                headers=headers_asaas, params=params, timeout=30)
            log_msg(f"  Status: {resp.status_code}", True)
            if resp.status_code != 200:
                log_msg(f"  ERRO HTTP! Corpo: {resp.text[:500]}", True)
                break
            data = resp.json()
            batch = data.get("data", [])
            all_raw.extend(batch)
            if not data.get("hasMore", False) or len(batch) == 0:
                break
            offset += limit
        except Exception as e:
            log_msg(f"  ❌ EXCEÇÃO: {type(e).__name__}: {str(e)}", True)
            break

    from collections import Counter
    log_msg(f"[ASAAS] Bruto: {len(all_raw)} | tipos: {dict(Counter(t.get('type') for t in all_raw))}", True)
    vistos = set()
    for t in all_raw:
        if t.get("type") in ASAAS_INCOME_TYPES and t.get("id") not in vistos:
            vistos.add(t.get("id"))
            t["_nome"] = asaas_nome(t, headers_asaas)
            transactions.append(t)
    log_msg(f"[ASAAS] Sem nome resolvido: {sum(1 for t in transactions if not t.get('_nome'))}", True)
    log_msg(f"[ASAAS] Receitas mantidas: {len(transactions)} | soma: {sum(float(t.get('value',0)) for t in transactions):.2f}", True)

    log_msg(f"\n[ASAAS] TOTAL: {len(transactions)} transações", True)
    return transactions


_ADVBOX_CACHE = None
_CACHE_PROC = {}
_CACHE_FAT = {}
_LAWSUIT_IDX = None
_ADVBOX_RAW = []
_SETTINGS = {}
pendentes_sem_tese = []

def fetch_advbox_transactions():
    """Busca Advbox (limite da API: 30 req/min -> espera entre páginas e repete em 429)"""
    global _ADVBOX_CACHE
    if DRY_RUN and _ADVBOX_CACHE is not None:
        return list(_ADVBOX_CACHE)
    res = _fetch_advbox_transactions()
    if DRY_RUN:
        _ADVBOX_CACHE = list(res)
    return res

def _fetch_advbox_transactions():
    transactions = []
    headers_advbox = {
        "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    log_msg(f"\n[ADVBOX] Iniciando fetch", True)

    offset = 0
    limit = 1000
    all_raw = []
    max_pages = 400  # Limite máximo de páginas para não ficar puxando dados eternamente
    page_count = 0
    filter_counts = {
        "type_not_income": 0,
        "status_not_paid": 0,
        "debit_bank_not_asaas": 0,
        "date_mismatch": 0,
        "kept": 0,
    }

    while page_count < max_pages:
        try:
            params = {"limit": limit, "offset": offset}
            log_msg(f"  Requisição: offset={offset}, limit={limit}", False)

            import time
            for _tent in range(6):
                resp = requests.get(
                    "https://app.advbox.com.br/api/v1/transactions",
                    headers=headers_advbox,
                    params=params,
                    timeout=60
                )
                if resp.status_code != 429:
                    break
                log_msg("  429 (limite da API) - aguardando 30s", True)
                time.sleep(30)
            time.sleep(2.2)

            log_msg(f"  Status: {resp.status_code}", True)
            log_msg(f"  Headers resposta: {dict(resp.headers)}", False)

            if resp.status_code != 200:
                log_msg(f"  ERRO HTTP! Corpo: {resp.text[:500]}", True)
                break

            data = resp.json()
            log_msg(f"  Chaves: {list(data.keys())}", True)
            batch = data.get("data", []) or data.get("transactions", [])
            log_msg(f"  Batch size (RAW): {len(batch)}", True)

            for idx, tx in enumerate(batch):
                all_raw.append(tx)
                tx_type = tx.get("entry_type")
                tx_status = "paid" if tx.get("date_payment") else None
                tx_debit = tx.get("debit_bank")
                tx_date = tx.get("date_payment") or ""

                log_msg(f"  TX[{idx}] type={tx_type} status={tx_status} debit_bank={tx_debit} date={tx_date}", False)

                if tx_type != "income":
                    filter_counts["type_not_income"] += 1
                    log_msg(f"    → FILTRADA (type)", False)
                    continue
                if tx_status != "paid":
                    filter_counts["status_not_paid"] += 1
                    log_msg(f"    → FILTRADA (status)", False)
                    continue
                if str(tx_debit or "").upper() != "ASAAS":
                    filter_counts["debit_bank_not_asaas"] += 1
                    log_msg(f"    → FILTRADA (debit_bank)", False)
                    continue
                if tx_date[:10] != TARGET_DATE:
                    filter_counts["date_mismatch"] += 1
                    log_msg(f"    → FILTRADA (date)", False)
                    continue

                filter_counts["kept"] += 1
                transactions.append(tx)
                log_msg(f"    → MANTIDA", False)

            page_count += 1

            if len(batch) < limit:
                log_msg(f"  Fim da paginação", True)
                break
            offset += limit

        except Exception as e:
            log_msg(f"  ❌ EXCEÇÃO: {type(e).__name__}: {str(e)}", True)
            break

    log_msg(f"\n[ADVBOX] === RESUMO DE FILTROS ===", True)
    log_msg(f"  Raw: {len(all_raw)} | type!=income: {filter_counts['type_not_income']} | status!=paid: {filter_counts['status_not_paid']} | debit!=ASAAS: {filter_counts['debit_bank_not_asaas']} | date!=target: {filter_counts['date_mismatch']} | MANTIDAS: {filter_counts['kept']}", True)
    log_msg(f"[ADVBOX] TOTAL: {len(transactions)} transações", True)

    global _ADVBOX_RAW
    _ADVBOX_RAW = all_raw
    return transactions


# ---------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ---------------------------------------------------------------------------
if not ASAAS_TOKEN or not ADVBOX_TOKEN:
    log_msg(f"\n❌ ERRO CRÍTICO: Tokens não fornecidos!", True)
    if ASAAS_TOKEN:
        log_msg(f"  ✓ ASAAS_TOKEN: definido ({len(ASAAS_TOKEN)} chars)", True)
    else:
        log_msg(f"  ✗ ASAAS_TOKEN: VAZIO ou NÃO DEFINIDO", True)
    if ADVBOX_TOKEN:
        log_msg(f"  ✓ ADVBOX_TOKEN: definido ({len(ADVBOX_TOKEN)} chars)", True)
    else:
        log_msg(f"  ✗ ADVBOX_TOKEN: VAZIO ou NÃO DEFINIDO", True)
    sys.exit(1)

log_msg(f"\n🔄 INICIANDO LOOP DE RECONCILIAÇÃO", True)

headers_advbox = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

attempt = 0
reconciliation_complete = False
all_corrections = []
divergencias_atuais = {}
total_asaas_final = 0
total_advbox_final = 0

while attempt < MAX_RECONCILIATION_ATTEMPTS and not reconciliation_complete:
    attempt += 1
    log_msg(f"\n{'='*100}\nTENTATIVA {attempt}/{MAX_RECONCILIATION_ATTEMPTS}\n{'='*100}", True)

    log_msg(f"\n[LEITURA 1] Buscando transações...", True)
    asaas_transactions = fetch_asaas_transactions()
    advbox_transactions = fetch_advbox_transactions()

    total_asaas = sum(float(tx.get("value", 0)) for tx in asaas_transactions)
    total_advbox = sum(
        float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
        for tx in advbox_transactions
    )

    log_msg(f"\nAsaas:  {len(asaas_transactions)} tx | R$ {total_asaas:.2f}", True)
    log_msg(f"Advbox: {len(advbox_transactions)} tx | R$ {total_advbox:.2f}", True)

    log_msg(f"\n[MATCHING] Identificando divergências...", True)

    # Passo 0: excluir transações de investimento do Asaas — já lançadas na conta de investimentos do Advbox
    # Exemplos: "Lvmx I. E. I. L.", fundos de investimento, FIDC, etc.
    investimentos_excluidos = []
    asaas_filtrado = []
    for a_tx in asaas_transactions:
        n_asaas_up = (a_tx.get("_nome") or "").upper()
        cpf_raw = (a_tx.get("_cpf") or "").replace(".","").replace("-","").replace("/","")
        eh_investimento = (any(inv in n_asaas_up for inv in NOMES_INVESTIMENTO)
                           or cpf_raw in CNPJS_INVESTIMENTO)
        if eh_investimento:
            v = round(float(a_tx.get("value", 0)), 2)
            log_msg(f"  ⚙️  Investimento excluído: {mascara_nome(a_tx.get('_nome'))} R${v} — já lançado na conta de investimentos", True)
            investimentos_excluidos.append(a_tx)
        else:
            asaas_filtrado.append(a_tx)
    if investimentos_excluidos:
        log_msg(f"  → {len(investimentos_excluidos)} transação(ões) de investimento excluídas da conciliação", True)
    asaas_transactions = asaas_filtrado

    def val_adv(tx):
        return round(float(str(tx.get("value", tx.get("amount", 0))).replace(",", ".")), 2)

    # Passo 1: valor E nome iguais
    restantes_adv = list(advbox_transactions)
    matched = []
    sobra_asaas = []
    for a_tx in asaas_transactions:
        v = round(float(a_tx.get("value", 0)), 2)
        n = norm_nome(a_tx.get("_nome"))
        achou = None
        for i, b_tx in enumerate(restantes_adv):
            if val_adv(b_tx) == v and n and norm_nome(b_tx.get("name")) == n:
                achou = i
                break
        if achou is None:
            sobra_asaas.append(a_tx)
        else:
            matched.append((a_tx, restantes_adv.pop(achou), v))

    # Passo 1b: pagadores judiciais (Caixa, Banco do Brasil, etc.) pagam êxito em nome do cliente
    # Nesses casos, o Asaas registra o banco como pagador mas o lançamento certo já está no Advbox.
    # Aceitar como conciliado se: pagador Asaas contém "CAIXA" ou "CEF" e o lançamento Advbox
    # tem categoria de êxito (EXITO na categoria) — match apenas por valor.
    PAGADORES_JUDICIAIS = ("CAIXA", "CEF", "BANCO DO BRASIL", "BB PAGAMENTOS", "SICOOB", "BRADESCO")
    sobra_asaas2 = []
    for a_tx in sobra_asaas:
        n_asaas = norm_nome(a_tx.get("_nome") or "")
        eh_pagador_judicial = any(p in n_asaas for p in PAGADORES_JUDICIAIS)
        if not eh_pagador_judicial:
            sobra_asaas2.append(a_tx)
            continue
        v = round(float(a_tx.get("value", 0)), 2)
        # Buscar lançamento Advbox com mesmo valor e categoria de êxito
        achou = None
        for i, b_tx in enumerate(restantes_adv):
            if val_adv(b_tx) == v:
                cat = str(b_tx.get("category_name") or b_tx.get("category") or "").upper()
                if "EXITO" in cat or "ÊXITO" in cat or "SUCUMB" in cat:
                    achou = i
                    break
        if achou is None:
            sobra_asaas2.append(a_tx)
        else:
            log_msg(f"  ✅ Pagador judicial ({n_asaas[:20]}) aceito como conciliado por valor R${v}", True)
            matched.append((a_tx, restantes_adv.pop(achou), v))
    sobra_asaas = sobra_asaas2

    # Passo 1c: pagadores intermediários Bemol/BMP — a Bemol processa pagamentos de clientes
    # e aparece no Asaas como pagador (CNPJ Bemol 35.410.271/0001-08 ou BMP 34.337.707/0001-00).
    # O lançamento no Advbox já deve estar atribuído ao cliente contratante, não à Bemol.
    # Aceitar como conciliado se: CNPJ Asaas é Bemol/BMP e existe lançamento Advbox com mesmo valor
    # em QUALQUER categoria de honorários (iniciais, êxito ou sucumbência).
    CNPJS_BEMOL = ("35410271000108", "34337707000100")  # Bemol + BMP (crédito Bemol)
    CATS_HONORARIOS = ("HONOR", "EXITO", "ÊXITO", "SUCUMB", "INICIAL", "FINAL")
    sobra_asaas3 = []
    for a_tx in sobra_asaas:
        cpf_raw = (a_tx.get("_cpf") or "").replace(".", "").replace("-", "").replace("/", "")
        eh_bemol = cpf_raw in CNPJS_BEMOL
        if not eh_bemol:
            sobra_asaas3.append(a_tx)
            continue
        v = round(float(a_tx.get("value", 0)), 2)
        # Buscar lançamento Advbox com mesmo valor e categoria de honorários
        achou = None
        for i, b_tx in enumerate(restantes_adv):
            if val_adv(b_tx) == v:
                cat = str(b_tx.get("category_name") or b_tx.get("category") or "").upper()
                if any(c in cat for c in CATS_HONORARIOS) or cat == "":
                    achou = i
                    break
        if achou is None:
            # Tentar match só por valor (sem restrição de categoria) como fallback
            achou = next((i for i, b_tx in enumerate(restantes_adv) if val_adv(b_tx) == v), None)
        if achou is None:
            sobra_asaas3.append(a_tx)
        else:
            n_bemol = mascara_nome(a_tx.get("_nome"))
            log_msg(f"  ✅ Pagador Bemol/BMP ({n_bemol}) aceito como conciliado por valor R${v}", True)
            matched.append((a_tx, restantes_adv.pop(achou), v))
    sobra_asaas = sobra_asaas3

    # Passo 1d: pagadores intermediários Bemol/BMP — repasse AGREGADO.
    # A Bemol às vezes repassa, numa ÚNICA transação no Asaas, a soma de vários fechamentos
    # de clientes diferentes (cada um já lançado separadamente no Advbox, por cliente/tese).
    # Nesse caso não há 1 lançamento Advbox com o mesmo valor — há VÁRIOS que SOMADOS batem.
    # Procurar, entre os lançamentos Advbox ainda não conciliados, uma combinação (2 a 4 itens)
    # cuja soma bata com o valor da transação Bemol/BMP (tolerância de 1 centavo).
    import itertools
    sobra_asaas4 = []
    for a_tx in sobra_asaas3:
        cpf_raw = (a_tx.get("_cpf") or "").replace(".", "").replace("-", "").replace("/", "")
        eh_bemol = cpf_raw in CNPJS_BEMOL
        if not eh_bemol:
            sobra_asaas4.append(a_tx)
            continue
        v = round(float(a_tx.get("value", 0)), 2)
        candidatos = [
            (i, b_tx) for i, b_tx in enumerate(restantes_adv)
            if any(c in str(b_tx.get("category_name") or b_tx.get("category") or "").upper() for c in CATS_HONORARIOS)
            or str(b_tx.get("category_name") or b_tx.get("category") or "") == ""
        ]
        achou_combo = None
        for r in (2, 3, 4):
            if achou_combo:
                break
            if len(candidatos) < r:
                continue
            for combo in itertools.combinations(candidatos, r):
                soma = round(sum(val_adv(b_tx) for _, b_tx in combo), 2)
                if abs(soma - v) <= TOLERANCE:
                    achou_combo = combo
                    break
        if achou_combo is None:
            sobra_asaas4.append(a_tx)
        else:
            n_bemol = mascara_nome(a_tx.get("_nome"))
            nomes_combo = [mascara_nome(b_tx.get("name")) for _, b_tx in achou_combo]
            log_msg(f"  ✅ Pagador Bemol/BMP ({n_bemol}) aceito como conciliado por COMBINAÇÃO de {len(achou_combo)} lançamento(s) somando R${v}: {nomes_combo}", True)
            idxs_remover = sorted((i for i, _ in achou_combo), reverse=True)
            for i in idxs_remover:
                restantes_adv.pop(i)
            matched.append((a_tx, achou_combo[0][1], v))
    sobra_asaas = sobra_asaas4

    # Passo 1e: repasse de êxito de pagador judicial (Caixa etc.) — lê o NÚMERO DO PROCESSO na cobrança do Asaas,
    # acha o processo/cliente/tese no Advbox e prepara a receita cheia (os honorários já lançados viram "modelo").
    caixa_planos = []
    sobra_asaas5 = []
    for a_tx in sobra_asaas:
        n_asaas = norm_nome(a_tx.get("_nome") or "")
        if not (any(p in n_asaas for p in PAGADORES_JUDICIAIS) and a_tx.get("_proc_longas")):
            sobra_asaas5.append(a_tx)
            continue
        v = round(float(a_tx.get("value", 0)), 2)
        lei = processo_do_repasse(a_tx, headers_advbox)
        modelo = None
        if lei:
            for i, b_tx in enumerate(restantes_adv):
                if b_tx.get("entry_type") == "income" and b_tx.get("lawsuit_id") == lei.get("id") and val_adv(b_tx) < v:
                    modelo = i
                    break
        if lei is None or modelo is None:
            log_msg(f"  ⚠️ Repasse judicial R${v}: processo/honorários não encontrados no Advbox - fica pendente", True)
            sobra_asaas5.append(a_tx)
            continue
        fee_tx = restantes_adv.pop(modelo)
        log_msg(f"  ✅ Repasse de êxito R${v}: processo achado (id {lei.get('id')}) - receita cheia será lançada", True)
        caixa_planos.append((a_tx, fee_tx, lei, v))
        matched.append((a_tx, fee_tx, v))
    sobra_asaas = sobra_asaas5

    # Passo 1f: acordo pago em PARTES — vários TEDs do mesmo pagador judicial cuja SOMA bate com 1 lançamento
    # de êxito/sucumbência no Advbox (ex.: acordo de R$ 11.000 pago em 2 TEDs).
    jud = [a for a in sobra_asaas if any(p in norm_nome(a.get("_nome") or "") for p in PAGADORES_JUDICIAIS)]
    for b_i in range(len(restantes_adv) - 1, -1, -1):
        b_tx = restantes_adv[b_i]
        cat = str(b_tx.get("category_name") or b_tx.get("category") or "").upper()
        if not ("EXITO" in cat or "ÊXITO" in cat or "SUCUMB" in cat) or len(jud) < 2:
            continue
        alvo_v = val_adv(b_tx)
        achou_g = None
        for r_ in (2, 3):
            for g in itertools.combinations(jud, r_):
                if abs(round(sum(float(x.get("value", 0)) for x in g), 2) - alvo_v) <= TOLERANCE:
                    achou_g = g
                    break
            if achou_g:
                break
        if achou_g:
            log_msg(f"  ✅ Acordo pago em {len(achou_g)} parte(s) somando R${alvo_v} conciliado com 1 lançamento de êxito", True)
            restantes_adv.pop(b_i)
            for x in achou_g:
                sobra_asaas.remove(x)
                jud.remove(x)
                matched.append((x, b_tx, round(float(x.get("value", 0)), 2)))

    # Passo 1g: recebimento do Asaas sem par no dia, mas o lançamento certo JÁ EXISTE no Advbox
    # (mesmo cliente, mesmo valor, vencimento = dia) com a data de pagamento errada ou sem baixa.
    # Em vez de criar duplicado, corrige a data de pagamento para o dia do recebimento.
    corrigir_datas = []
    ids_usados = {str(b.get("id")) for _, b, _ in matched}
    sobra_asaas6 = []
    for a_tx in sobra_asaas:
        v = round(float(a_tx.get("value", 0)), 2)
        n = norm_nome(a_tx.get("_nome"))
        cand = None
        if n:
            for t in _ADVBOX_RAW:
                if (t.get("entry_type") == "income" and str(t.get("debit_bank") or "").upper() == "ASAAS"
                        and norm_nome(t.get("name")) == n and val_adv(t) == v
                        and str(t.get("date_due") or "")[:10] == TARGET_DATE
                        and str(t.get("date_payment") or "")[:10] != TARGET_DATE
                        and str(t.get("id")) not in ids_usados):
                    cand = t
                    break
        if cand is None and n:
            # Parcela de consultoria/parceria: o lançamento já existe em aberto (previsto, vencimento de outro dia).
            # Dá baixa na parcela em aberto MAIS ANTIGA do mesmo cliente e valor, em vez de criar outra.
            abertas = [t for t in _ADVBOX_RAW
                       if t.get("entry_type") == "income" and str(t.get("debit_bank") or "").upper() == "ASAAS"
                       and not t.get("date_payment")
                       and (str(t.get("category") or "").startswith("HONORÁRIOS CONSULTORIAS")
                            or str(t.get("category") or "").endswith("INICIAIS-CONSULTORIA")
                            or "PARCEIROS" in str(t.get("category") or "").upper()
                            or str(t.get("cost_center") or "").upper() == "PARCERIAS")
                       and _so_alnum(t.get("name")) == _so_alnum(n) and val_adv(t) == v
                       and str(t.get("id")) not in ids_usados]
            abertas.sort(key=lambda t: str(t.get("date_due") or ""))
            if abertas:
                cand = abertas[0]
        if cand is None:
            sobra_asaas6.append(a_tx)
        else:
            log_msg(f"  🔧 Lançamento {cand.get('id')} (R${v}) já existe com data de pagamento diferente - será corrigida para {TARGET_DATE}", True)
            ids_usados.add(str(cand.get("id")))
            corrigir_datas.append((cand, v))
            matched.append((a_tx, cand, v))
    sobra_asaas = sobra_asaas6

    # Passo 2: mesmo valor, nome diferente -> divergência de NOME (só relatar, não corrigir sozinho)
    nome_diferente = []
    unmatched_asaas = []
    for a_tx in sobra_asaas:
        v = round(float(a_tx.get("value", 0)), 2)
        achou = next((i for i, b_tx in enumerate(restantes_adv) if val_adv(b_tx) == v), None)
        if achou is None:
            unmatched_asaas.append(a_tx)
        else:
            nome_diferente.append((a_tx, restantes_adv.pop(achou)))
    unmatched_advbox = restantes_adv

    divergencias_atuais = {
        "nome_diferente": [
            {"valor": round(float(a.get("value", 0)), 2), "asaas": mascara_nome(a.get("_nome")),
             "advbox": mascara_nome(b.get("name")), "advbox_id": b.get("id")}
            for a, b in nome_diferente],
        "faltando_no_advbox": [
            {"valor": round(float(a.get("value", 0)), 2), "cliente_asaas": mascara_nome(a.get("_nome"))}
            for a in unmatched_asaas],
        "fantasmas_no_advbox": [
            {"valor": val_adv(b), "cliente_advbox": mascara_nome(b.get("name")), "advbox_id": b.get("id")}
            for b in unmatched_advbox],
    }
    log_msg(f"Matches (valor+nome): {len(matched)} | Nome diferente: {len(nome_diferente)} | Faltando: {len(unmatched_asaas)} | Fantasmas: {len(unmatched_advbox)}", True)
    log_msg(f"Divergências: {json.dumps(divergencias_atuais, ensure_ascii=False)}", True)

    # Correções
    corr_antes = len(all_corrections)
    if unmatched_advbox and not DRY_RUN:
        log_msg(f"\n[CORRIGINDO] Desmarcando pagamento de {len(unmatched_advbox)} lançamento(s) que não batem (não apaga)...", True)
        for tx in unmatched_advbox:
            tx_id = tx.get("id", "")
            valor = val_adv(tx)
            if tx_id:
                if unpay_advbox_transaction(tx_id, headers_advbox):
                    all_corrections.append(("DESMARCAR_PAGAMENTO", valor))

    if corrigir_datas and not DRY_RUN:
        log_msg(f"\n[CORRIGINDO] Ajustando data de pagamento de {len(corrigir_datas)} lançamento(s) existente(s)...", True)
        for cand, v in corrigir_datas:
            ok = pagar_lancamento_existente(cand.get("id"), TARGET_DATE, v, headers_advbox)
            log_msg(f"  AJUSTAR DATA {cand.get('id')}: {'ok' if ok else 'FALHOU'}", True)
            if ok:
                all_corrections.append(("AJUSTAR_DATA", v))

    if caixa_planos and not DRY_RUN:
        log_msg(f"\n[CORRIGINDO] Lançando receita cheia de {len(caixa_planos)} repasse(s) de êxito...", True)
        for plano in caixa_planos:
            if lancar_receita_exito_caixa(plano, headers_advbox):
                all_corrections.append(("CREATE", plano[3]))

    if unmatched_asaas and not DRY_RUN:
        log_msg(f"\n[CORRIGINDO] Criando {len(unmatched_asaas)} faltante(s)...", True)
        for tx in unmatched_asaas:
            valor = float(tx.get("value", 0))
            if create_advbox_transaction(tx, headers_advbox):
                all_corrections.append(("CREATE", valor))

    any_ok_this_attempt = len(all_corrections) > corr_antes

    # Dupla checagem
    log_msg(f"\n[DUPLA CHECAGEM] Relendo...", True)
    asaas_transactions_check = fetch_asaas_transactions()
    advbox_transactions_check = fetch_advbox_transactions()

    # Aplicar mesmo filtro de investimento na dupla checagem
    asaas_transactions_check = [
        tx for tx in asaas_transactions_check
        if not (any(inv in (tx.get("_nome") or "").upper() for inv in NOMES_INVESTIMENTO)
                or (tx.get("_cpf") or "").replace(".","").replace("-","").replace("/","") in CNPJS_INVESTIMENTO)
    ]
    total_asaas_final = sum(float(tx.get("value", 0)) for tx in asaas_transactions_check)
    total_advbox_final = sum(
        float(str(tx.get("value", tx.get("amount", 0))).replace(",", "."))
        for tx in advbox_transactions_check
    )

    diferenca = abs(total_asaas_final - total_advbox_final)

    log_msg(f"\nAsaas (dupla):  R$ {total_asaas_final:.2f}", True)
    log_msg(f"Advbox (dupla): R$ {total_advbox_final:.2f}", True)
    log_msg(f"Diferença: R$ {diferenca:.2f}", True)

    sem_divergencia = not (unmatched_asaas or unmatched_advbox or nome_diferente)
    if (unmatched_asaas or unmatched_advbox) and not DRY_RUN and not any_ok_this_attempt:
        log_msg("⛔ Nenhuma correção funcionou nesta tentativa - parando para não gastar chamadas da API.", True)
        break
    if diferenca < TOLERANCE and sem_divergencia:
        log_msg(f"\n✅ VALORES E NOMES BATEM!", True)
        reconciliation_complete = True
    else:
        if attempt < MAX_RECONCILIATION_ATTEMPTS:
            log_msg(f"⚠️  Tentando novamente...", True)
        else:
            log_msg(f"❌ Limite de tentativas atingido", True)

def revisao_do_mes(headers_asaas, headers_advbox):
    """REVISÃO antes de dar a conciliação como feita: do dia 1 do mês até o dia anterior ao alvo,
    soma da receita do Asaas (sem investimento) x soma do Advbox (conta ASAAS, por data de pagamento), dia a dia."""
    from datetime import date, timedelta
    alvo = date.fromisoformat(TARGET_DATE)
    d = alvo.replace(day=1)
    dias_div = []
    while d < alvo:
        iso = d.isoformat()
        off, vistos, tot_a = 0, set(), 0.0
        while True:
            j = requests.get("https://api.asaas.com/v3/financialTransactions", headers=headers_asaas,
                             params={"startDate": iso, "finishDate": iso, "limit": 100, "offset": off}, timeout=30).json()
            for t in j.get("data", []):
                if t["id"] in vistos or t.get("type") not in ASAAS_INCOME_TYPES:
                    continue
                vistos.add(t["id"])
                nome = (asaas_nome(t, headers_asaas) or "").upper()
                if any(k in nome for k in NOMES_INVESTIMENTO):
                    continue
                tot_a += float(t.get("value", 0))
            if not j.get("hasMore") or not j.get("data"):
                break
            off += 100
        tot_b = sum(float(str(t.get("amount", 0)).replace(",", ".")) for t in _ADVBOX_RAW
                    if t.get("entry_type") == "income" and str(t.get("debit_bank") or "").upper() == "ASAAS"
                    and str(t.get("date_payment") or "")[:10] == iso)
        if abs(tot_a - tot_b) >= TOLERANCE:
            dias_div.append({"dia": iso, "asaas": round(tot_a, 2), "advbox": round(tot_b, 2), "diferenca": round(tot_a - tot_b, 2)})
        d += timedelta(days=1)
    return dias_div


# REVISÃO DO MÊS (regra do escritório: só é conciliação feita se o mês até aqui também fechar)
revisao_mes = []
try:
    revisao_mes = revisao_do_mes({"access_token": ASAAS_TOKEN, "Accept": "application/json"},
                                 {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    if revisao_mes:
        log_msg(f"⚠️ REVISÃO DO MÊS: {len(revisao_mes)} dia(s) anteriores não fecham: {revisao_mes}", True)
        reconciliation_complete = False
    else:
        log_msg("✅ REVISÃO DO MÊS: todos os dias anteriores fecham", True)
except Exception as e:
    log_msg(f"⚠️ revisão do mês não concluída: {type(e).__name__}: {e}", True)

# RELATÓRIO FINAL
log_msg(f"\n{'='*100}\nRESULTADO FINAL\n{'='*100}", True)

if reconciliation_complete:
    log_msg(f"✅ CONCILIAÇÃO OK em {attempt} tentativa(s)", True)
else:
    log_msg(f"❌ NÃO CONCILIADA após {attempt} tentativa(s)", True)

log_msg(f"  Asaas: R$ {total_asaas_final:.2f}", True)
log_msg(f"  Advbox: R$ {total_advbox_final:.2f}", True)
log_msg(f"  Diferença: R$ {abs(total_asaas_final - total_advbox_final):.2f}", True)
log_msg(f"  Correções: {len(all_corrections)}", True)

# Relatório JSON
report = {
    "data": TARGET_DATE,
    "gerado_em": datetime.now().isoformat(),
    "status": "CONCILIADO" if reconciliation_complete else "NAO_CONCILIADO",
    "tentativas": attempt,
    "max_tentativas": MAX_RECONCILIATION_ATTEMPTS,
    "totais_finais": {
        "asaas": round(total_asaas_final, 2),
        "advbox": round(total_advbox_final, 2),
        "diferenca": round(abs(total_asaas_final - total_advbox_final), 2),
    },
    "divergencias": divergencias_atuais,
    "pendentes_sem_tese": pendentes_sem_tese,
    "revisao_mes": revisao_mes,
    "correcoes": {
        "total_realizadas": len(all_corrections),
        "detalhes": [
            {"tipo": corr[0], "valor": round(corr[1], 2)}
            for corr in all_corrections
        ],
    },
}

nome_relatorio = f"relatorio_{TARGET_DATE}.json"
with open(nome_relatorio, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

log_msg(f"\n📄 Relatório: {nome_relatorio}", True)
log_msg(f"📋 Log detalhado: {LOG_FILE}", True)
log_msg(f"\n{'='*100}\nFIM DO LOG\n{'='*100}", True)
