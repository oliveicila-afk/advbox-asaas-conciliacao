#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Checagem intradiária de recebimento de êxito (Asaas -> Advbox, conta da contadoria).

Faz uma única coisa:
  1. Pega os recebimentos do dia na Asaas (TED/pagamento de tribunal, Caixa).
  2. Quando o externalReference traz o número do processo (CNJ), identifica o
     processo no Advbox e o cliente dele.
  3. Procura na conta da contadoria (lançamentos de receita, banco ASAAS) o
     lançamento desse processo/cliente, com o mesmo valor e SEM data de pagamento.
  4. Se achar exatamente 1, preenche a data de pagamento com o dia em que o valor entrou.

NÃO altera categoria, centro de custo, número de processo nem valor. Se houver
mais de um candidato, ou se a data de pagamento já estiver preenchida, não mexe
e só registra no log.

Variáveis de ambiente:
  ADVBOX_TOKEN     token Bearer do Advbox (secret do GitHub)
  ASAAS_TOKEN      access_token da Asaas (secret do GitHub)
  TIMEZONE         opcional, padrão America/Cuiaba
  TARGET_DATE      opcional, AAAA-MM-DD; sem ele, usa o dia de hoje
  DRY_RUN          opcional, "true" simula sem gravar no Advbox
  MODO_LOOP        opcional, "true" repete a checagem a cada INTERVALO_MINUTOS
                   dentro da janela HORA_INICIO..HORA_FIM (uso local)
"""

import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "").strip()
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "").strip()
TIMEZONE = os.environ.get("TIMEZONE", "America/Cuiaba")
DRY_RUN = os.environ.get("DRY_RUN", "false").strip().lower() == "true"

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ASAAS_BASE = "https://api.asaas.com/v3"

# Conta da contadoria no Advbox (mesmo valor usado pela conciliação)
DEBIT_ACCOUNT_ASAAS = 193264
USERS_ID_PADRAO = 65747

# Recebimentos que contam como receita
TIPOS_RECEITA = {"PAYMENT_RECEIVED", "RECEIVABLE_ANTICIPATION_GROSS_CREDIT"}

# A API do Advbox recusa PUT parcial: o payload precisa vir completo (testado
# no projeto). Por isso buscamos o detalhe antes de alterar.
PAUSA_ENTRE_CHAMADAS = 2.2
USER_AGENT = "Mozilla/5.0"


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


# --------------------------------------------------------------------------
# Utilidades de texto e valor
# --------------------------------------------------------------------------

def normalizar_nome(nome: str) -> str:
    if not nome:
        return ""
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    nome = re.sub(r"[^a-zA-Z0-9 ]", " ", nome)
    return re.sub(r"\s+", " ", nome).strip().lower()


def centavos_iguais(a: float, b: float, tolerancia: float = 0.01) -> bool:
    return abs(round(a, 2) - round(b, 2)) <= tolerancia


def extrair_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def formatar_valor_advbox(valor: float) -> str:
    # A API do Advbox grava errado com ponto decimal; o formato certo é com vírgula
    return f"{valor:.2f}".replace(".", ",")


def identificar_processo_por_referencia(external_reference: str, lawsuits: list[dict]) -> dict | None:
    """O TED de tribunal/Caixa traz o número do processo (CNJ) no externalReference,
    sem pontuação e às vezes com zeros à frente. Só devolve um processo quando
    casa com exatamente 1 candidato; 0 ou mais de 1 fica sem identificação."""
    digitos_ref = extrair_digitos(external_reference)
    if len(digitos_ref) < 15:
        return None
    achados = []
    for lw in lawsuits:
        digitos_processo = extrair_digitos(lw.get("process_number") or "")
        if len(digitos_processo) < 15:
            continue
        if digitos_processo in digitos_ref or digitos_ref.endswith(digitos_processo):
            achados.append(lw)
    return achados[0] if len(achados) == 1 else None


# --------------------------------------------------------------------------
# Advbox
# --------------------------------------------------------------------------

def _headers_advbox() -> dict:
    return {
        "Authorization": f"Bearer {ADVBOX_TOKEN}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }


def advbox_get(path: str, params: dict | None = None, tentativas: int = 5):
    url = f"{ADVBOX_BASE}{path}"
    for tentativa in range(1, tentativas + 1):
        resp = requests.get(url, headers=_headers_advbox(), params=params or {}, timeout=30)
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                log(f"Advbox {path}: 200 mas corpo não é JSON (tentativa {tentativa})")
        else:
            log(f"Advbox GET {path} -> {resp.status_code} (tentativa {tentativa}/{tentativas})")
        time.sleep(min(2 ** tentativa, 20))
    raise RuntimeError(f"Falha ao consultar Advbox {path} após {tentativas} tentativas")


def _paginar(path: str, limite: int = 1000, limite_paginas: int = 50) -> list[dict]:
    todos, offset = [], 0
    for _ in range(limite_paginas):
        pagina = advbox_get(path, {"limit": limite, "offset": offset})
        itens = pagina if isinstance(pagina, list) else pagina.get("data", [])
        if not itens:
            break
        todos.extend(itens)
        if len(itens) < limite:
            break
        offset += limite
        time.sleep(0.4)
    return todos


def advbox_lancamentos_conta_contadoria() -> list[dict]:
    """Lançamentos do banco ASAAS (conta da contadoria). A listagem não filtra por
    data, então paginamos tudo e filtramos aqui."""
    todos = _paginar("/transactions")
    do_banco = [
        i for i in todos
        if (i.get("debit_bank") or i.get("bank") or "").upper() == "ASAAS"
    ]
    log(f"Advbox: {len(todos)} lançamentos no total, {len(do_banco)} da conta ASAAS")
    return do_banco


def advbox_processos() -> list[dict]:
    todos = _paginar("/lawsuits")
    log(f"Advbox: {len(todos)} processos")
    return todos


def advbox_detalhe_lancamento(tx_id) -> dict:
    return advbox_get(f"/transactions/{tx_id}")


def advbox_salvar_data_pagamento(detalhe: dict, data_pagamento: str) -> bool:
    """Regrava o lançamento com o payload completo, mudando só date_payment."""
    tx_id = detalhe.get("id")
    payload = {
        "entry_type": detalhe.get("entry_type") or "income",
        "users_id": detalhe.get("users_id") or USERS_ID_PADRAO,
        "debit_account": DEBIT_ACCOUNT_ASAAS,
        "categories_id": detalhe.get("categories_id"),
        "cost_centers_id": detalhe.get("cost_centers_id"),
        "customers_id": detalhe.get("customers_id"),
        "lawsuits_id": detalhe.get("lawsuits_id"),
        "amount": formatar_valor_advbox(float(detalhe.get("amount") or 0)),
        "date_due": str(detalhe.get("date_due") or "")[:10],
        "date_payment": data_pagamento,
        "description": detalhe.get("description") or "",
    }
    payload = {k: v for k, v in payload.items() if v is not None and v != ""}

    url = f"{ADVBOX_BASE}/transactions/{tx_id}"
    headers = {**_headers_advbox(), "Content-Type": "application/json"}
    if DRY_RUN:
        log(f"[DRY RUN] PUT {tx_id} <- date_payment={data_pagamento}")
        return True
    resp = requests.put(url, headers=headers, json=payload, timeout=30)
    time.sleep(PAUSA_ENTRE_CHAMADAS)
    if resp.status_code in (200, 204):
        return True
    log(f"Advbox PUT /transactions/{tx_id} -> {resp.status_code}: {resp.text[:200]}")
    return False


# --------------------------------------------------------------------------
# Asaas
# --------------------------------------------------------------------------

def asaas_recebimentos_do_dia(data_alvo: str) -> list[dict]:
    todos, offset, limite = [], 0, 100
    while True:
        resp = requests.get(
            f"{ASAAS_BASE}/financialTransactions",
            headers={"access_token": ASAAS_TOKEN},
            params={"startDate": data_alvo, "finishDate": data_alvo, "limit": limite, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        pagina = resp.json()
        itens = pagina.get("data", [])
        if not itens:
            break
        todos.extend(itens)
        if not pagina.get("hasMore"):
            break
        offset += limite
        time.sleep(0.3)
    do_dia = [i for i in todos if i.get("date") == data_alvo and i.get("type") in TIPOS_RECEITA]
    log(f"Asaas: {len(do_dia)} recebimentos em {data_alvo}")
    return do_dia


# --------------------------------------------------------------------------
# Casamento e checagem
# --------------------------------------------------------------------------

def achar_lancamentos_contadoria(processo: dict, valor: float, lancamentos: list[dict]) -> list[dict]:
    """Lançamentos de receita que batem com o processo/cliente, com o mesmo valor e
    ainda sem data de pagamento. Só age quando devolve exatamente 1."""
    digitos_processo = extrair_digitos(processo.get("process_number") or "")
    nomes_cliente = {
        normalizar_nome(c.get("name") or "") for c in (processo.get("customers") or [])
    }
    nomes_cliente.discard("")

    candidatos = []
    for item in lancamentos:
        if item.get("entry_type") != "income":
            continue
        if item.get("date_payment"):
            continue
        if not centavos_iguais(valor, float(item.get("amount") or 0)):
            continue
        mesmo_processo = bool(digitos_processo) and (
            extrair_digitos(item.get("process_number") or "") == digitos_processo
        )
        nome_item = normalizar_nome(item.get("name") or item.get("customer_name") or "")
        mesmo_cliente = bool(nome_item) and any(
            n in nome_item or nome_item in n for n in nomes_cliente
        )
        if mesmo_processo or mesmo_cliente:
            candidatos.append(item)
    return candidatos


def checar(data_alvo: str) -> dict:
    lancamentos = advbox_lancamentos_conta_contadoria()
    recebimentos = asaas_recebimentos_do_dia(data_alvo)

    resultado = {"marcados": [], "falhas": [], "ambiguos": [], "sem_processo": []}
    ids_marcados = set()
    processos = None

    for item in recebimentos:
        ref = item.get("externalReference") or ""
        valor = float(item.get("value", 0))
        descricao = item.get("description") or item.get("customerName") or ref

        if not ref:
            resultado["sem_processo"].append(descricao)
            continue

        if processos is None:
            # só busca os processos quando há recebimento com referência, uma vez por rodada
            processos = advbox_processos()
        processo = identificar_processo_por_referencia(ref, processos)
        if not processo:
            resultado["sem_processo"].append(descricao)
            continue

        cliente = (processo.get("customers") or [{}])[0].get("name")
        registro = {"cliente": cliente, "processo": processo.get("process_number"), "valor": valor}

        candidatos = [
            c for c in achar_lancamentos_contadoria(processo, valor, lancamentos)
            if c.get("id") not in ids_marcados
        ]
        if len(candidatos) != 1:
            registro["candidatos"] = len(candidatos)
            resultado["ambiguos"].append(registro)
            continue

        alvo = candidatos[0]
        detalhe = advbox_detalhe_lancamento(alvo["id"])
        time.sleep(PAUSA_ENTRE_CHAMADAS)
        if detalhe.get("date_payment"):
            resultado["ambiguos"].append({**registro, "candidatos": "já pago"})
            continue

        registro["transaction_id"] = alvo["id"]
        if advbox_salvar_data_pagamento(detalhe, data_alvo):
            ids_marcados.add(alvo["id"])
            resultado["marcados"].append(registro)
        else:
            resultado["falhas"].append(registro)

    return resultado


def data_alvo_padrao() -> str:
    override = os.environ.get("TARGET_DATE", "").strip()
    if override:
        return override
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")


def executar_uma_vez(data_alvo: str) -> None:
    log(f"Checagem de êxito do dia {data_alvo}{' [DRY RUN]' if DRY_RUN else ''}")
    r = checar(data_alvo)
    for m in r["marcados"]:
        log(f"MARCADO recebido {data_alvo}: {m['cliente']} | {m['processo']} | R$ {m['valor']:.2f}")
    for a in r["ambiguos"]:
        log(f"AMBIGUO (não mexido, candidatos={a['candidatos']}): {a['cliente']} | {a['processo']} | R$ {a['valor']:.2f}")
    for f in r["falhas"]:
        log(f"FALHA ao marcar: {f['cliente']} | {f['processo']} | R$ {f['valor']:.2f}")
    log(
        f"RESUMO êxito: {len(r['marcados'])} marcados | {len(r['ambiguos'])} ambíguos | "
        f"{len(r['falhas'])} falhas | {len(r['sem_processo'])} sem processo identificado"
    )


def main() -> None:
    if not ADVBOX_TOKEN or not ASAAS_TOKEN:
        log("ERRO: ADVBOX_TOKEN e/ou ASAAS_TOKEN não configurados. Abortando.")
        sys.exit(1)

    if os.environ.get("MODO_LOOP", "false").strip().lower() != "true":
        executar_uma_vez(data_alvo_padrao())
        return

    intervalo = int(os.environ.get("INTERVALO_MINUTOS", "30"))
    inicio = int(os.environ.get("HORA_INICIO", "8"))
    fim = int(os.environ.get("HORA_FIM", "19"))
    log(f"Modo contínuo: a cada {intervalo} min, entre {inicio}h e {fim}h ({TIMEZONE})")
    while True:
        hora = datetime.now(ZoneInfo(TIMEZONE)).hour
        if inicio <= hora < fim:
            try:
                executar_uma_vez(data_alvo_padrao())
            except Exception as exc:  # uma falha de API não derruba o loop
                log(f"ERRO nesta rodada (tenta de novo no próximo ciclo): {exc}")
        else:
            log("Fora da janela de funcionamento, aguardando.")
        time.sleep(intervalo * 60)


if __name__ == "__main__":
    main()
