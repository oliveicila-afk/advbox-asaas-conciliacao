#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conciliação diária Advbox x Asaas.

O que este script faz sozinho, todo dia (v1.1):
  1. Lê os lançamentos do Advbox (banco ASAAS) e os eventos financeiros do
     dia anterior na Asaas.
  2. Aplica as regras de negócio já validadas com a Priscila.
  3. CORRIGE SOZINHO só os dois casos considerados seguros/não-ambíguos:
       (a) data de pagamento errada ou vazia num lançamento que já existe
           no Advbox, quando há exatamente 1 correspondência clara na Asaas
           (nome + valor batendo, sem outro candidato concorrendo);
       (b) criação do lançamento consolidado das taxas diárias (TAXA DE
           COMUNICAÇÃO, TAXA DE ANTECIPAÇÃO, TAXA DE EMISSÃO DE NF), que
           não têm cliente/processo vinculado, quando falta valor pra
           bater com a Asaas do dia.
  4. Tudo o mais (taxas bancárias por cliente, pagamentos órfãos
     institucionais, transferências, estornos, qualquer coisa que exija
     identificar QUAL cliente/processo) fica só no relatório, pra decisão
     da Priscila — o robô não decide isso sozinho.
  5. Gera um PDF com o resultado (o que foi corrigido, o que ficou
     pendente) e manda por email.
  6. (novo, 22/09/2026) Pra receita "faltando" que não bate por nome com
     nada no Advbox — típico de TED recebido direto de tribunal/Caixa
     Econômica, sem o CPF/nome do cliente — tenta IDENTIFICAR (não lançar!)
     o processo/cliente batendo os dígitos do campo externalReference da
     Asaas contra o número do processo (CNJ) de cada lawsuit no Advbox.
     Quando acha um candidato único, mostra no PDF "Possível processo
     identificado: ... conferir Histórico > Tarefas no Advbox antes de
     lançar" — porque só olhando as tarefas do processo (campo que a API
     do Advbox não expõe) dá pra saber se o valor é honorário SUCUMBENCIAL
     ou CONTRATUAL, e se tem repasse a fazer pro cliente. Também busca o
     cadastro do cliente (Pessoas) e, pelo campo "Origem da pessoa", tenta
     sugerir um centro de custo (mesmo padrão "GRUPO-CANAL" descoberto no
     caso Weliton Lopes de Oliveira em 22/09/2026). O robô nunca decide
     isso sozinho nem lança nada a partir dessa identificação — só aponta.

Variáveis de ambiente esperadas (Secrets no GitHub):
  ADVBOX_TOKEN     -> token Bearer da API do Advbox
  ASAAS_TOKEN      -> access_token da API do Asaas
  SMTP_USER        -> email usado para ENVIAR (conta Gmail)
  SMTP_PASS        -> senha de app do Gmail (não é a senha normal da conta)
  EMAIL_DESTINO    -> email que vai RECEBER o relatório
  TARGET_DATE      -> opcional, AAAA-MM-DD. Se não vier, usa "ontem".
  TIMEZONE         -> opcional, padrão "America/Manaus"
  DRY_RUN          -> opcional, "true" pra simular as correções sem
                       gravar de verdade no Advbox (só loga o que faria)
"""

import os
import re
import sys
import time
import smtplib
import unicodedata
from datetime import datetime, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import requests
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# --------------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------------

ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
EMAIL_DESTINO = os.environ.get("EMAIL_DESTINO", "")
TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
DRY_RUN = os.environ.get("DRY_RUN", "false").strip().lower() == "true"

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ASAAS_BASE = "https://api.asaas.com/v3"

# IDs já confirmados nas sessões anteriores de conciliação (ver memória do
# projeto / histórico de conciliação com a Priscila).
COST_CENTER_DESPESAS_FINANCEIRAS_GERAL = 60814
DEBIT_ACCOUNT_ASAAS = 193264
USERS_ID_PRISCILA = 65747
CATEGORIES_ID_TAXAS_BANCARIAS = 51  # por cliente, precisa customers_id/lawsuits_id — fica manual

# As 3 taxas "diárias consolidadas" — sem cliente/processo vinculado.
# Chave = campo "type" que vem no /financialTransactions da Asaas.
TAXAS_DIARIAS_CONSOLIDADAS = {
    "INSTANT_TEXT_MESSAGE_FEE": {"categories_id": 70703, "nome": "TAXA DE COMUNICAÇÃO"},
    "RECEIVABLE_ANTICIPATION_FEE": {"categories_id": 94787, "nome": "TAXA DE ANTECIPAÇÃO"},
    "INVOICE_FEE": {"categories_id": 70704, "nome": "TAXA DE EMISSÃO DE NF"},
}

# Tipos de evento financeiro na Asaas que contam como RECEITA do dia
TIPOS_RECEITA = {"PAYMENT_RECEIVED", "RECEIVABLE_ANTICIPATION_GROSS_CREDIT"}
# Taxa por cliente (fica só no relatório, não é criada sozinha)
TIPO_TAXA_BANCARIA_CLIENTE = "PAYMENT_FEE"
# Liquidação interna de algo já antecipado antes — não é despesa nova
TIPOS_IGNORAR_INFORMATIVO = {"RECEIVABLE_ANTICIPATION_DEBIT"}
# Estornos — tratados à parte (regra de par saída+estorno mesmo mês/valor)
TIPOS_ESTORNO = {"PIX_TRANSACTION_DEBIT_REFUND", "PAYMENT_REFUND"}
# Transferências — sempre ficam pra classificação manual (natureza varia)
TIPOS_TRANSFER = {"TRANSFER"}

TODOS_TIPOS_CONHECIDOS = (
    TIPOS_RECEITA
    | set(TAXAS_DIARIAS_CONSOLIDADAS.keys())
    | {TIPO_TAXA_BANCARIA_CLIENTE}
    | TIPOS_IGNORAR_INFORMATIVO
    | TIPOS_ESTORNO
    | TIPOS_TRANSFER
)


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def normalizar_nome(nome: str) -> str:
    """Remove acento, pontuação e caixa pra comparar nomes com segurança."""
    if not nome:
        return ""
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    nome = re.sub(r"[^a-zA-Z0-9 ]", " ", nome)
    nome = re.sub(r"\s+", " ", nome).strip().lower()
    return nome


def centavos_iguais(a: float, b: float, tolerancia: float = 0.01) -> bool:
    return abs(round(a, 2) - round(b, 2)) <= tolerancia


def formatar_valor_advbox(valor: float) -> str:
    """
    BUG conhecido da API do Advbox: enviar amount com ponto decimal (ex:
    7.92 ou "7.92") faz o sistema salvar errado (vira 792). A forma
    correta é string com VÍRGULA (ex: "7,92"). Nunca mude isso sem testar
    de novo contra a API real.
    """
    return f"{valor:.2f}".replace(".", ",")


# --------------------------------------------------------------------------
# Advbox — leitura
# --------------------------------------------------------------------------

ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
# Sem um User-Agent de navegador de verdade, o Cloudflare do Advbox devolve
# uma página de desafio (403 HTML) em vez de chamar a API — descoberto ao
# testar direto de uma sessão em nuvem. Sem isso, o robô do GitHub Actions
# corre o mesmo risco (o User-Agent padrão do requests/Python também é
# bloqueado).


def advbox_get(path: str, params: dict | None = None, tentativas: int = 5) -> dict:
    url = f"{ADVBOX_BASE}{path}"
    headers = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": ADVBOX_USER_AGENT, "Accept": "application/json"}
    for tentativa in range(1, tentativas + 1):
        resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                log(f"Advbox devolveu 200 mas corpo não é JSON válido em {path} — tentativa {tentativa}")
        else:
            log(f"Advbox GET {path} -> status {resp.status_code} (tentativa {tentativa}/{tentativas})")
        time.sleep(min(2 ** tentativa, 20))
    raise RuntimeError(f"Falha ao consultar Advbox {path} após {tentativas} tentativas")


def advbox_get_all_transactions(limite_paginas: int = 50) -> list[dict]:
    """
    O endpoint de listagem do Advbox ignora silenciosamente os parâmetros de
    data (bug já confirmado em sessões anteriores) — por isso pagina tudo e
    filtra no lado de cá. `limite_paginas` é uma trava de segurança (não
    pra rodar pra sempre se algo sair do esperado).
    """
    log("Advbox: paginando /transactions (filtro é feito no lado de cá)…")
    todos = []
    offset = 0
    limite = 1000
    for _ in range(limite_paginas):
        pagina = advbox_get("/transactions", {"limit": limite, "offset": offset})
        itens = pagina if isinstance(pagina, list) else pagina.get("data", [])
        if not itens:
            break
        todos.extend(itens)
        if len(itens) < limite:
            break
        offset += limite
        time.sleep(0.4)
    else:
        log(f"AVISO: atingiu o limite de {limite_paginas} páginas — pode haver mais registros não lidos.")

    do_banco_asaas = [
        item for item in todos
        if (item.get("debit_bank") or item.get("bank") or "").upper() == "ASAAS"
    ]
    log(f"Advbox: {len(todos)} lançamentos lidos no total, {len(do_banco_asaas)} do banco ASAAS")
    return do_banco_asaas


# --------------------------------------------------------------------------
# Advbox — escrita (só os dois casos seguros)
# --------------------------------------------------------------------------

def advbox_put(transaction_id, payload: dict) -> bool:
    url = f"{ADVBOX_BASE}/transactions/{transaction_id}"
    headers = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": ADVBOX_USER_AGENT, "Accept": "application/json"}
    if DRY_RUN:
        log(f"[DRY RUN] PUT {url} <- {payload}")
        return True
    try:
        resp = requests.put(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            return True
        log(f"Advbox PUT /transactions/{transaction_id} -> status {resp.status_code}: {resp.text[:300]}")
        return False
    except requests.RequestException as exc:
        log(f"Advbox PUT /transactions/{transaction_id} -> erro de conexão: {exc}")
        return False


def advbox_post(payload: dict) -> dict | None:
    url = f"{ADVBOX_BASE}/transactions"
    headers = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": ADVBOX_USER_AGENT, "Accept": "application/json"}
    if DRY_RUN:
        log(f"[DRY RUN] POST {url} <- {payload}")
        return {"id": "DRY_RUN", "simulado": True}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in (200, 201):
            try:
                return resp.json()
            except ValueError:
                return {"status": "criado_sem_corpo_json"}
        log(f"Advbox POST /transactions -> status {resp.status_code}: {resp.text[:300]}")
        return None
    except requests.RequestException as exc:
        log(f"Advbox POST /transactions -> erro de conexão: {exc}")
        return None


# --------------------------------------------------------------------------
# Asaas
# --------------------------------------------------------------------------

def advbox_get_all_lawsuits(limite_paginas: int = 20) -> list[dict]:
    """Busca todos os processos (lawsuits) cadastrados no Advbox — usado só
    pra tentar identificar, por número de processo, receitas que caíram
    direto na Asaas sem bater por nome (ver identificar_processo_por_referencia).
    """
    todos, offset, limite = [], 0, 1000
    for _ in range(limite_paginas):
        pagina = advbox_get("/lawsuits", {"limit": limite, "offset": offset})
        itens = pagina if isinstance(pagina, list) else pagina.get("data", [])
        if not itens:
            break
        todos.extend(itens)
        if len(itens) < limite:
            break
        offset += limite
        time.sleep(0.3)
    log(f"Advbox: {len(todos)} processos (lawsuits) no total")
    return todos


def asaas_get(path: str, params: dict | None = None, tentativas: int = 5) -> dict:
    url = f"{ASAAS_BASE}{path}"
    headers = {"access_token": ASAAS_TOKEN}
    for tentativa in range(1, tentativas + 1):
        resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                log(f"Asaas devolveu 200 mas corpo não é JSON válido em {path} — tentativa {tentativa}")
        else:
            log(f"Asaas {path} -> status {resp.status_code} (tentativa {tentativa}/{tentativas})")
        time.sleep(min(2 ** tentativa, 20))
    raise RuntimeError(f"Falha ao consultar Asaas {path} após {tentativas} tentativas")


def asaas_get_financial_transactions_do_dia(data_alvo: str) -> list[dict]:
    """
    O filtro por 'type' da Asaas já se mostrou não confiável em sessões
    anteriores — por isso pedimos por intervalo de data e AINDA filtramos
    no cliente pelo campo 'date' (que já reflete o creditDate/dia real).
    """
    log(f"Asaas: buscando /financialTransactions de {data_alvo}…")
    todos = []
    offset = 0
    limite = 100
    while True:
        pagina = asaas_get(
            "/financialTransactions",
            {"startDate": data_alvo, "finishDate": data_alvo, "limit": limite, "offset": offset},
        )
        itens = pagina.get("data", [])
        if not itens:
            break
        todos.extend(itens)
        if not pagina.get("hasMore"):
            break
        offset += limite
        time.sleep(0.3)

    do_dia = [item for item in todos if item.get("date") == data_alvo]
    log(f"Asaas: {len(do_dia)} eventos financeiros em {data_alvo} (de {len(todos)} lidos)")
    return do_dia


# --------------------------------------------------------------------------
# Matching (nome + valor) contra TODO o histórico do Advbox, não só o dia
# --------------------------------------------------------------------------

def encontrar_candidatos(nome_asaas: str, valor: float, advbox_itens: list[dict]) -> list[dict]:
    nome_norm = normalizar_nome(nome_asaas)
    candidatos = []
    for item in advbox_itens:
        nome_adv = normalizar_nome(item.get("name") or item.get("customer_name") or "")
        valor_adv = float(item.get("amount", 0) or 0)
        if not (nome_norm and nome_adv):
            continue
        if (nome_norm in nome_adv or nome_adv in nome_norm) and centavos_iguais(valor, valor_adv):
            candidatos.append(item)
    return candidatos


# --------------------------------------------------------------------------
# Análise
# --------------------------------------------------------------------------

def extrair_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def identificar_processo_por_referencia(external_reference: str, lawsuits: list[dict]) -> dict | None:
    """Descoberto em 22/09/2026 (casos Weliton Lopes de Oliveira e Lucas
    Monteiro Gazel): um pagamento que cai direto na Asaas via TED de
    tribunal/Caixa Econômica — sem CPF/nome do cliente batendo com nada no
    Advbox — traz o número do processo (formato CNJ) embutido no campo
    "externalReference" do evento financeiro, só que sem os tracinhos/pontos
    e às vezes com zeros de preenchimento na frente.

    Aqui a gente tenta casar os dígitos desse campo com os dígitos do
    process_number de algum processo (lawsuit) no Advbox. Só retorna um
    resultado quando encontra exatamente 1 candidato — 0 ou mais de 1 fica
    ambíguo e não é reportado (evita falso positivo).

    IMPORTANTE — isso só IDENTIFICA um candidato de processo/cliente. Nunca
    decide sozinho se o valor é honorário SUCUMBENCIAL ou CONTRATUAL, nem se
    tem repasse a fazer pro cliente — isso só dá pra confirmar abrindo
    Histórico > Tarefas do processo no Advbox (a API não expõe esse dado),
    então o robô nunca lança nada a partir disso, só aponta o caminho.
    """
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
    if len(achados) == 1:
        return achados[0]
    return None


def advbox_get_customer(customer_id) -> dict | None:
    try:
        return advbox_get(f"/customers/{customer_id}")
    except RuntimeError as exc:
        log(f"Não consegui buscar cliente {customer_id} no Advbox: {exc}")
        return None


def sugerir_centro_custo_por_origem(origem_cliente: str, advbox_itens: list[dict]) -> str | None:
    """Descoberto em 22/09/2026 (caso Weliton Lopes de Oliveira): os centros
    de custo no Advbox seguem o padrão "GRUPO-CANAL" (ex: "PROFESSOR/PEDAGOGO
    -PROSPECÇÃO ATIVA", "CONSUMIDOR-INDICAÇÃO") e costumam bater com palavras
    do campo "Origem da pessoa" do cadastro do cliente em Pessoas no Advbox
    (formato "CANAL | ... | GRUPO | ..." — ex: "PROSPECÇÃO | PROMOÇÃO
    HORIZONTAL | PROFESSOR | SEDUC | AM").

    Aqui a gente procura, entre os nomes de centro de custo que já aparecem
    nos lançamentos que o robô buscou pra conciliação de hoje (advbox_itens
    — não faz nenhuma chamada extra à API pra isso), um cujo GRUPO (antes do
    hífen) e CANAL (depois do hífen) batam cada um com pelo menos uma palavra
    do campo origem. Só sugere um NOME de centro de custo quando acha
    exatamente 1 candidato — nunca decide/lança nada sozinho, e a Priscila
    ainda confirma antes de qualquer lançamento."""
    def _palavras(texto: str, tamanho_minimo: int = 4) -> set[str]:
        # tamanho mínimo evita colisão boba tipo "AM" (Amazonas, no fim da
        # origem) casando por substring com "instAGRAM" de um centro de
        # custo qualquer — exige palavra inteira normalizada, não pedaço
        return {p for p in normalizar_nome(texto).split(" ") if len(p) >= tamanho_minimo}

    palavras_origem: set[str] = set()
    for pedaco in re.split(r"[|,]", origem_cliente or ""):
        palavras_origem |= _palavras(pedaco)
    if not palavras_origem:
        return None

    nomes_centro_custo = {item.get("cost_center") for item in advbox_itens if item.get("cost_center")}
    candidatos = []
    for nome in nomes_centro_custo:
        partes = nome.split("-", 1)
        if len(partes) != 2:
            continue
        palavras_grupo, palavras_canal = _palavras(partes[0]), _palavras(partes[1])
        if (palavras_origem & palavras_grupo) and (palavras_origem & palavras_canal):
            candidatos.append(nome)
    if len(candidatos) == 1:
        return candidatos[0]
    return None


def sugerir_categoria_por_precedente_do_processo(
    numero_processo: str, advbox_itens: list[dict]
) -> dict | None:
    """Descoberto em 22/09/2026, revisão multi-dia 10-21/09: quando o
    processo identificado (via identificar_processo_por_referencia) JÁ tem
    algum lançamento de honorário anterior no Advbox (outro pagamento do
    mesmo processo, ex: o honorário inicial ou uma parcela anterior de
    êxito/sucumbencial), a categoria e o centro de custo usados nesse
    lançamento anterior são um sinal muito mais confiável do que tentar
    adivinhar pela "Origem da pessoa" — na prática, de 8 casos reais
    verificados nessa revisão, 5 bateram exato ou quase exato com o
    lançamento anterior do mesmo processo (Axon, Stanley, Daniel, Jefferson,
    e parcialmente Alessandro), contra só 1 de 8 em que a Origem da pessoa
    sozinha dava um palpite utilizável (João Marcelo).

    Procura, dentro dos lançamentos já lidos do Advbox (advbox_itens, sem
    chamada extra à API), algum outro lançamento de RECEITA (entry_type
    income) do mesmo número de processo cuja categoria contenha "ÊXITO",
    "SUCUMBENCIAL" ou "HONORÁRIOS" (ou seja, é um honorário, não uma taxa/
    despesa administrativa) — e devolve a categoria e o centro de custo
    usados lá. Quando encontra mais de uma categoria diferente pro mesmo
    processo, devolve None (ambíguo, evita palpite errado). Só uma
    SUGESTÃO — nunca decide nem lança nada sozinho; ainda precisa confirmar
    se esse pagamento novo é sucumbencial ou contratual (com repasse) antes
    de usar essa categoria, porque a categoria de honorário de êxito e a de
    sucumbencial do mesmo processo podem ser diferentes."""
    digitos_alvo = extrair_digitos(numero_processo or "")
    if len(digitos_alvo) < 15:
        return None
    palavras_honorario = ("ÊXITO", "EXITO", "SUCUMBENCIAL", "HONOR")
    achados = {}
    for item in advbox_itens:
        if item.get("entry_type") != "income":
            continue
        if extrair_digitos(item.get("process_number") or "") != digitos_alvo:
            continue
        categoria = (item.get("category") or "").upper()
        if not any(p in categoria for p in palavras_honorario):
            continue
        cost_center = item.get("cost_center")
        achados[(item.get("category"), cost_center)] = item.get("category")
    if len(achados) == 1:
        (categoria, cost_center) = next(iter(achados.keys()))
        return {"categoria": categoria, "cost_center": cost_center}
    return None


def enriquecer_receita_faltando_com_processo(
    relatorio: dict, lawsuits: list[dict], advbox_itens: list[dict]
) -> None:
    """Pra cada item de receita_faltando, tenta achar um processo candidato
    (ver identificar_processo_por_referencia) e guarda a info junto do item,
    pra aparecer no PDF como pista — nunca lança nada sozinho. Quando acha o
    processo, tenta duas fontes de sugestão pra categoria/centro de custo,
    nessa ordem de confiança: (1) precedente de outro lançamento de
    honorário do mesmo processo (ver
    sugerir_categoria_por_precedente_do_processo — mais confiável, testado
    em 22/09/2026), e (2) busca o cadastro do cliente (Pessoas) pra sugerir
    um centro de custo pelo campo "Origem da pessoa" (ver
    sugerir_centro_custo_por_origem — usada só quando não achou precedente).
    Ambas são só sugestão, nunca decidem/lançam nada sozinhas."""
    for item in relatorio["receita_faltando"]:
        ref = item.get("externalReference") or ""
        if not ref:
            continue
        lw = identificar_processo_por_referencia(ref, lawsuits)
        if lw:
            clientes = lw.get("customers") or []
            customer_id = clientes[0].get("customer_id") if clientes else None
            numero_processo = lw.get("process_number")

            categoria_sugerida_por_precedente = None
            centro_custo_sugerido = None
            precedente = sugerir_categoria_por_precedente_do_processo(numero_processo, advbox_itens)
            if precedente:
                categoria_sugerida_por_precedente = precedente["categoria"]
                centro_custo_sugerido = precedente["cost_center"]

            if not centro_custo_sugerido and customer_id:
                cliente = advbox_get_customer(customer_id)
                if cliente and cliente.get("origin"):
                    centro_custo_sugerido = sugerir_centro_custo_por_origem(
                        cliente["origin"], advbox_itens
                    )

            item["_processo_identificado"] = {
                "processo": numero_processo,
                "cliente": (clientes[0].get("name") if clientes else None),
                "estagio": lw.get("stage"),
                "lawsuits_id": lw.get("id"),
                "categoria_sugerida_por_precedente": categoria_sugerida_por_precedente,
                "centro_custo_sugerido": centro_custo_sugerido,
            }


def montar_relatorio(data_alvo: str, advbox_itens: list[dict], asaas_itens: list[dict]) -> dict:
    receita_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_RECEITA]
    taxa_bancaria_asaas = [i for i in asaas_itens if i.get("type") == TIPO_TAXA_BANCARIA_CLIENTE]
    informativo_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_IGNORAR_INFORMATIVO]
    estorno_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_ESTORNO]
    transfer_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_TRANSFER]
    outros_asaas = [i for i in asaas_itens if i.get("type") not in TODOS_TIPOS_CONHECIDOS]

    # --- Receita: casar cada evento da Asaas com o Advbox (dia certo,
    # dia errado, ou realmente faltando) ---
    receita_ok, receita_data_errada, receita_faltando = [], [], []
    for item in receita_asaas:
        nome = (item.get("description") or "") + " " + (item.get("customerName") or "")
        valor = float(item.get("value", 0))
        candidatos = encontrar_candidatos(nome, valor, advbox_itens)
        candidatos_no_dia = [c for c in candidatos if c.get("date_payment") == data_alvo]
        if candidatos_no_dia:
            receita_ok.append(item)
        elif len(candidatos) == 1:
            receita_data_errada.append({"asaas": item, "advbox": candidatos[0]})
        else:
            receita_faltando.append(item)

    # --- Taxa bancária por cliente: mesmo raciocínio, mas NUNCA corrige
    # sozinho (precisa customers_id/lawsuits_id) — só reporta ---
    taxa_bancaria_ok, taxa_bancaria_data_errada, taxa_bancaria_faltando = [], [], []
    for item in taxa_bancaria_asaas:
        nome = (item.get("description") or "") + " " + (item.get("customerName") or "")
        valor = abs(float(item.get("value", 0)))
        candidatos = encontrar_candidatos(nome, valor, advbox_itens)
        candidatos_no_dia = [c for c in candidatos if c.get("date_payment") == data_alvo]
        if candidatos_no_dia:
            taxa_bancaria_ok.append(item)
        elif len(candidatos) == 1:
            taxa_bancaria_data_errada.append({"asaas": item, "advbox": candidatos[0]})
        else:
            taxa_bancaria_faltando.append(item)

    # --- Taxas diárias consolidadas: comparação por TOTAL do dia, não por
    # item — não têm cliente/processo, então não faz sentido "casar" um a
    # um ---
    taxas_diarias_info = {}
    for tipo_asaas, meta in TAXAS_DIARIAS_CONSOLIDADAS.items():
        total_asaas = sum(
            abs(float(i.get("value", 0))) for i in asaas_itens if i.get("type") == tipo_asaas
        )
        # BUG corrigido (achado numa revisão manual em 11/09/2026): a listagem
        # paginada /transactions (sem filtro de data) NUNCA devolve o campo
        # "categories_id" (numérico) — só "category" (nome, string). Comparar
        # por categories_id aqui sempre dava 0 falsamente e fazia o robô tentar
        # criar o consolidado do dia inteiro de novo mesmo quando já existia
        # (causou uma duplicata real de TAXA DE ANTECIPAÇÃO no dia 08/09,
        # já corrigida manualmente).
        total_advbox = sum(
            float(i.get("amount", 0) or 0)
            for i in advbox_itens
            if (i.get("category") or "").strip().upper() == meta["nome"].strip().upper()
            and i.get("date_payment") == data_alvo
        )
        taxas_diarias_info[tipo_asaas] = {
            "nome": meta["nome"],
            "categories_id": meta["categories_id"],
            "total_asaas": total_asaas,
            "total_advbox": total_advbox,
            "faltando": round(total_asaas - total_advbox, 2),
        }

    total_receita_asaas = sum(float(i.get("value", 0)) for i in receita_asaas)
    # BUG corrigido: receita_ok guarda o ITEM DA ASAAS (não o do Advbox) —
    # ler "amount" nele (campo do Advbox) sempre devolvia 0 e fazia o
    # relatório mostrar "Advbox R$ 0,00" mesmo com tudo certo. Não afetava
    # quais itens eram corrigidos, só o total mostrado no resumo/PDF.
    total_receita_advbox = sum(float(i.get("value", 0)) for i in receita_ok) + sum(
        float(c["advbox"].get("amount", 0) or 0) for c in receita_data_errada
    )
    # nota: total_receita_advbox aqui reflete o que JÁ existe no Advbox pro
    # dia certo + o que existe mas está com data errada (mesmo dinheiro,
    # só mal datado) — não conta duas vezes.

    total_taxa_bancaria_asaas = sum(abs(float(i.get("value", 0))) for i in taxa_bancaria_asaas)
    total_taxas_diarias_asaas = sum(v["total_asaas"] for v in taxas_diarias_info.values())
    total_despesa_asaas = total_taxa_bancaria_asaas + total_taxas_diarias_asaas

    total_taxas_diarias_advbox = sum(v["total_advbox"] for v in taxas_diarias_info.values())
    total_taxa_bancaria_advbox = sum(
        abs(float(i.get("value", 0))) for i in taxa_bancaria_ok
    ) + sum(float(c["advbox"].get("amount", 0) or 0) for c in taxa_bancaria_data_errada)
    total_despesa_advbox = total_taxa_bancaria_advbox + total_taxas_diarias_advbox

    return {
        "data": data_alvo,
        "total_receita_asaas": total_receita_asaas,
        "total_receita_advbox": total_receita_advbox,
        "diferenca_receita": round(total_receita_asaas - total_receita_advbox, 2),
        "total_despesa_asaas": total_despesa_asaas,
        "total_despesa_advbox": total_despesa_advbox,
        "diferenca_despesa": round(total_despesa_asaas - total_despesa_advbox, 2),
        "receita_ok": receita_ok,
        "receita_data_errada": receita_data_errada,
        "receita_faltando": receita_faltando,
        "taxa_bancaria_data_errada": taxa_bancaria_data_errada,
        "taxa_bancaria_faltando": taxa_bancaria_faltando,
        "taxas_diarias_info": taxas_diarias_info,
        "estornos": estorno_asaas,
        "transferencias": transfer_asaas,
        "informativos_ignorados": informativo_asaas,
        "outros_nao_classificados": outros_asaas,
    }


# --------------------------------------------------------------------------
# Correções automáticas (só os 2 casos seguros)
# --------------------------------------------------------------------------

def aplicar_correcoes(relatorio: dict) -> dict:
    aplicadas = []
    falhas = []

    # (a) datas erradas em lançamento que JÁ EXISTE no Advbox (receita ou
    # taxa bancária por cliente) — só quando o candidato é único. Isso não
    # cria vínculo novo de cliente/processo nenhum, só corrige a data de
    # um lançamento que já estava corretamente identificado antes.
    pares_data_errada = [
        (par, "receita") for par in relatorio["receita_data_errada"]
    ] + [
        (par, "taxa bancária") for par in relatorio["taxa_bancaria_data_errada"]
    ]
    for par, categoria in pares_data_errada:
        advbox_item = par["advbox"]
        data_alvo = relatorio["data"]
        transaction_id = advbox_item.get("id") or advbox_item.get("transactions_id")
        descricao = advbox_item.get("name") or advbox_item.get("description") or f"id {transaction_id}"
        ok = advbox_put(transaction_id, {"date_due": data_alvo, "date_payment": data_alvo})
        registro = {
            "tipo": f"correção de data ({categoria})",
            "descricao": f"{descricao} — R$ {float(advbox_item.get('amount', 0)):.2f}",
            "id": transaction_id,
        }
        (aplicadas if ok else falhas).append(registro)

    # (b) criação das taxas diárias consolidadas que estão faltando
    for tipo_asaas, info in relatorio["taxas_diarias_info"].items():
        if info["faltando"] > 0.01:
            payload = {
                "users_id": USERS_ID_PRISCILA,
                "entry_type": "expense",
                "debit_account": DEBIT_ACCOUNT_ASAAS,
                "categories_id": info["categories_id"],
                "cost_centers_id": COST_CENTER_DESPESAS_FINANCEIRAS_GERAL,
                "amount": formatar_valor_advbox(info["faltando"]),
                "date_due": relatorio["data"],
                "date_payment": relatorio["data"],
                "description": f"{info['nome']} - consolidado do dia (conciliação automática)",
            }
            resultado = advbox_post(payload)
            registro = {
                "tipo": "criação de taxa diária",
                "descricao": f"{info['nome']} — R$ {info['faltando']:.2f}",
                "id": (resultado or {}).get("id"),
            }
            (aplicadas if resultado else falhas).append(registro)

    return {"aplicadas": aplicadas, "falhas": falhas}


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------

def sanitizar_texto_pdf(txt) -> str:
    """Deixa qualquer texto seguro pra desenhar no PDF com a fonte Helvetica
    (que só suporta Latin-1). Troca pontuação "esperta" comum (travessão,
    aspas curvas, reticências) pelo equivalente simples e, por segurança,
    qualquer caractere que ainda sobrar fora do Latin-1 — por exemplo um
    emoji ou símbolo vindo de uma descrição de lançamento da Advbox/Asaas —
    é substituído por "?" em vez de derrubar o relatório inteiro.
    """
    txt = str(txt)
    substituicoes = {
        "—": "-", "–": "-", "―": "-",
        "“": '"', "”": '"', "‘": "'", "’": "'",
        "…": "...", "\xa0": " ",
    }
    for de, para in substituicoes.items():
        txt = txt.replace(de, para)
    return txt.encode("latin-1", errors="replace").decode("latin-1")


def gerar_pdf(relatorio: dict, correcoes: dict, caminho_saida: str) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, sanitizar_texto_pdf(f"Conciliacao Advbox x Asaas - {relatorio['data']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    modo = " (DRY RUN - nada foi gravado de verdade)" if DRY_RUN else ""
    pdf.cell(0, 6, sanitizar_texto_pdf(f"Gerado automaticamente em {datetime.now().strftime('%d/%m/%Y %H:%M')}{modo}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    def titulo(txt):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(235, 235, 235)
        pdf.cell(0, 8, sanitizar_texto_pdf(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        pdf.set_font("Helvetica", "", 10)

    def linha(txt):
        # Faz a quebra de linha manualmente (em vez de usar multi_cell direto)
        # porque o fpdf2 tem um bug conhecido: quando o texto encosta quase
        # exatamente na borda da largura disponível, ele lança
        # "Not enough horizontal space to render a single character" em vez
        # de quebrar a linha (https://github.com/py-pdf/fpdf2/issues/1582).
        # Quebrando nós mesmos, com uma margem de segurança, evitamos cair
        # nesse caso extremo e o relatório nunca falha por causa de layout.
        # Também sanitiza o texto primeiro, porque descrições vindas da
        # Advbox/Asaas podem trazer caracteres (travessão, emoji, etc.) que a
        # fonte Helvetica não suporta e derrubariam o relatório inteiro.
        txt = sanitizar_texto_pdf(txt)
        largura_maxima = pdf.w - pdf.l_margin - pdf.r_margin - 2

        def escreve(texto):
            pdf.cell(0, 6, texto, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        palavras = txt.split(" ")
        linha_atual = ""
        for palavra in palavras:
            candidata = f"{linha_atual} {palavra}" if linha_atual else palavra
            if not linha_atual or pdf.get_string_width(candidata) <= largura_maxima:
                linha_atual = candidata
            else:
                escreve(linha_atual)
                linha_atual = palavra
        escreve(linha_atual)

    bateu_receita = abs(relatorio["diferenca_receita"]) < 0.02
    bateu_despesa = abs(relatorio["diferenca_despesa"]) < 0.02

    titulo("Resumo (apos as correcoes automaticas abaixo)")
    linha(f"Receita  - Asaas: R$ {relatorio['total_receita_asaas']:.2f}  |  Advbox: R$ {relatorio['total_receita_advbox']:.2f}  |  Diferenca: R$ {relatorio['diferenca_receita']:.2f}  {'(BATEU)' if bateu_receita else '(NAO BATEU)'}")
    linha(f"Despesa  - Asaas: R$ {relatorio['total_despesa_asaas']:.2f}  |  Advbox: R$ {relatorio['total_despesa_advbox']:.2f}  |  Diferenca: R$ {relatorio['diferenca_despesa']:.2f}  {'(BATEU)' if bateu_despesa else '(NAO BATEU)'}")
    linha("Obs: os totais do Advbox acima ja consideram as correcoes de data como se estivessem certas — a coluna 'Diferenca' mostra o que sobra mesmo depois de corrigir.")
    pdf.ln(2)

    titulo(f"Corrigido automaticamente ({len(correcoes['aplicadas'])})")
    if not correcoes["aplicadas"]:
        linha("Nada precisou de correcao automatica hoje.")
    for c in correcoes["aplicadas"]:
        linha(f"- [{c['tipo']}] {c['descricao']}")
    pdf.ln(2)

    if correcoes["falhas"]:
        titulo(f"Tentativas de correcao que FALHARAM ({len(correcoes['falhas'])}) - precisa checar na mao")
        for c in correcoes["falhas"]:
            linha(f"- [{c['tipo']}] {c['descricao']}")
        pdf.ln(2)

    titulo(f"Receita faltando no Advbox - precisa decisao manual ({len(relatorio['receita_faltando'])})")
    if not relatorio["receita_faltando"]:
        linha("Nenhuma pendencia encontrada.")
    for item in relatorio["receita_faltando"]:
        linha(f"- R$ {float(item.get('value', 0)):.2f} | {item.get('type')} | {item.get('description', '')}")
        pid = item.get("_processo_identificado")
        if pid:
            linha(
                f"    Possivel processo identificado: {pid.get('processo')} "
                f"- {pid.get('cliente') or 'nome do cliente nao encontrado'} "
                f"(estagio: {pid.get('estagio') or 'n/d'}). CONFERIR em "
                f"Historico > Tarefas desse processo no Advbox antes de lancar "
                f"(sucumbencial ou contratual, e se tem repasse a fazer pro cliente)."
            )
            if pid.get("categoria_sugerida_por_precedente"):
                linha(
                    f"    Categoria sugerida (por precedente de outro "
                    f"lancamento de honorario do mesmo processo): "
                    f"{pid['categoria_sugerida_por_precedente']} - confirmar "
                    f"se este pagamento e do mesmo tipo (exito/sucumbencial) "
                    f"antes de usar."
                )
            if pid.get("centro_custo_sugerido"):
                linha(
                    f"    Centro de custo sugerido: {pid['centro_custo_sugerido']} "
                    f"- confirmar antes de usar."
                )
    pdf.ln(2)

    titulo(f"Taxa bancaria por cliente faltando - precisa decisao manual ({len(relatorio['taxa_bancaria_faltando'])})")
    linha("(Datas divergentes de taxa bancaria ja aparecem corrigidas na secao 'Corrigido automaticamente' acima.)")
    if not relatorio["taxa_bancaria_faltando"]:
        linha("Nenhuma pendencia encontrada.")
    for item in relatorio["taxa_bancaria_faltando"]:
        linha(f"- FALTANDO: R$ {abs(float(item.get('value', 0))):.2f} | {item.get('description', '')}")
    pdf.ln(2)

    titulo(f"Transferencias do dia - precisam de classificacao manual ({len(relatorio['transferencias'])})")
    if not relatorio["transferencias"]:
        linha("Nenhuma transferencia no dia.")
    for item in relatorio["transferencias"]:
        linha(f"- R$ {float(item.get('value', 0)):.2f} | {item.get('description', '')}")
    pdf.ln(2)

    titulo(f"Estornos do dia - conferir regra de par saida+estorno ({len(relatorio['estornos'])})")
    if not relatorio["estornos"]:
        linha("Nenhum estorno no dia.")
    for item in relatorio["estornos"]:
        linha(f"- R$ {float(item.get('value', 0)):.2f} | {item.get('description', '')}")
    pdf.ln(2)

    if relatorio["outros_nao_classificados"]:
        titulo(f"Outros eventos nao classificados nas regras atuais ({len(relatorio['outros_nao_classificados'])})")
        for item in relatorio["outros_nao_classificados"]:
            linha(f"- R$ {float(item.get('value', 0)):.2f} | {item.get('type')} | {item.get('description', '')}")

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    linha(
        "O robo corrige sozinho SO: data de pagamento errada/vazia em lancamento ja existente "
        "(quando ha exatamente 1 correspondencia clara) e a criacao das taxas diarias consolidadas "
        "(comunicacao/antecipacao/emissao de NF, que nao tem cliente vinculado). Taxa bancaria por "
        "cliente, pagamentos orfaos institucionais e transferencias continuam exigindo decisao manual."
    )

    pdf.output(caminho_saida)
    log(f"PDF salvo em {caminho_saida}")


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------

def enviar_email(caminho_pdf: str, data_alvo: str, relatorio: dict, correcoes: dict) -> None:
    if not (SMTP_USER and SMTP_PASS and EMAIL_DESTINO):
        log("Credenciais de email incompletas — pulando envio (PDF ficou salvo localmente).")
        return

    bateu_receita = abs(relatorio["diferenca_receita"]) < 0.02
    bateu_despesa = abs(relatorio["diferenca_despesa"]) < 0.02
    status = "tudo bateu" if (bateu_receita and bateu_despesa) else "ha divergencias"

    msg = EmailMessage()
    prefixo_dry = "[DRY RUN] " if DRY_RUN else ""
    msg["Subject"] = f"{prefixo_dry}Conciliação Bancária - {data_alvo} ({status})"
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_DESTINO
    msg.set_content(
        f"Conciliacao automatica do dia {data_alvo}.\n\n"
        f"Receita: Asaas R$ {relatorio['total_receita_asaas']:.2f} x Advbox R$ {relatorio['total_receita_advbox']:.2f}\n"
        f"Despesa: Asaas R$ {relatorio['total_despesa_asaas']:.2f} x Advbox R$ {relatorio['total_despesa_advbox']:.2f}\n\n"
        f"Correcoes aplicadas automaticamente: {len(correcoes['aplicadas'])}\n"
        f"Falhas ao tentar corrigir: {len(correcoes['falhas'])}\n\n"
        "Detalhes completos no PDF em anexo."
    )

    with open(caminho_pdf, "rb") as f:
        msg.add_attachment(
            f.read(), maintype="application", subtype="pdf",
            filename=f"conciliacao_{data_alvo}.pdf",
        )

    log("Enviando email…")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)
    log("Email enviado.")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def data_padrao() -> str:
    tz = ZoneInfo(TIMEZONE)
    ontem = datetime.now(tz) - timedelta(days=1)
    return ontem.strftime("%Y-%m-%d")


def main() -> None:
    if not ADVBOX_TOKEN or not ASAAS_TOKEN:
        log("ERRO: ADVBOX_TOKEN e/ou ASAAS_TOKEN não configurados. Abortando.")
        sys.exit(1)

    data_alvo = os.environ.get("TARGET_DATE", "").strip() or data_padrao()
    log(f"Conciliando o dia {data_alvo} (fuso {TIMEZONE}){' [DRY RUN]' if DRY_RUN else ''}")

    advbox_itens = advbox_get_all_transactions()
    asaas_itens = asaas_get_financial_transactions_do_dia(data_alvo)

    relatorio = montar_relatorio(data_alvo, advbox_itens, asaas_itens)

    if relatorio["receita_faltando"]:
        # só busca os ~8 mil processos do Advbox quando realmente tem
        # receita faltando pra tentar identificar (evita esse custo todo
        # dia à toa) — ver enriquecer_receita_faltando_com_processo
        try:
            lawsuits = advbox_get_all_lawsuits()
            enriquecer_receita_faltando_com_processo(relatorio, lawsuits, advbox_itens)
        except RuntimeError as exc:
            log(f"Não consegui buscar processos do Advbox pra identificar receita faltando: {exc}")

    correcoes = aplicar_correcoes(relatorio)

    log(
        f"RESUMO — Receita: Asaas R$ {relatorio['total_receita_asaas']:.2f} x "
        f"Advbox R$ {relatorio['total_receita_advbox']:.2f} (dif. R$ {relatorio['diferenca_receita']:.2f}) | "
        f"Despesa: Asaas R$ {relatorio['total_despesa_asaas']:.2f} x "
        f"Advbox R$ {relatorio['total_despesa_advbox']:.2f} (dif. R$ {relatorio['diferenca_despesa']:.2f}) | "
        f"Corrigido: {len(correcoes['aplicadas'])} | Falhas: {len(correcoes['falhas'])}"
    )

    caminho_pdf = f"conciliacao_{data_alvo}.pdf"
    gerar_pdf(relatorio, correcoes, caminho_pdf)
    enviar_email(caminho_pdf, data_alvo, relatorio, correcoes)

    log("Concluído.")


if __name__ == "__main__":
    main()
