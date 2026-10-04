# 🏗️ Arquitetura Técnica — Agente Financeiro v2.0

## 🎯 Visão Geral

O agente v2.0 é um **sistema de automação de conciliação bancária** que roda em **GitHub Actions** (não em cloud — dados sensíveis ficam protegidos). Ele executa diariamente, compara saldos, calcula fluxo de caixa e gera relatórios mascarados.

---

## 🔌 Componentes Principais

### 1. **Orquestrador (GitHub Actions)**
```
.github/workflows/conciliacao-diaria.yml
  ↓
Agenda: cron "0 5 * * *" (1h da manhã em Manaus = 5 AM UTC)
Ambiente: Ubuntu 22.04 + Python 3.11
Permissões: Lê secrets, roda Python, faz upload de artifacts
```

**Fluxo:**
1. **Checkout** do código do repositório
2. **Setup Python** 3.11
3. **Instala dependências** (pip install -r requirements.txt)
4. **Executa** `python conciliar.py` (passando secrets como env vars)
5. **Sobe artifacts** (PDF) pra download por 30 dias

### 2. **Núcleo da Conciliação (conciliar_v2.py)**

#### **Entrada:**
- `ADVBOX_TOKEN`: Bearer token da API Advbox
- `ASAAS_TOKEN`: Access token da API Asaas
- `TARGET_DATE`: Data pra conciliar (padrão: ontem)
- `TIMEZONE`: Fuso horário (padrão: America/Manaus)
- `DRY_RUN`: bool (true = simula, false = grava de verdade)

#### **Saída:**
- `conciliacao_AAAA-MM-DD.pdf`: Relatório mascarado
- Email com resumo (se credentials SMTP configuradas)
- Log estruturado no GitHub Actions

---

## 📊 Fluxo de Dados (v2.0)

```
┌─────────────────────────────────────────────────────────────────┐
│                   GITHUB ACTIONS (1h da manhã)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  1️⃣ FETCH DO ADVBOX                                            │
├─────────────────────────────────────────────────────────────────┤
│  GET /transactions  (histórico completo)                        │
│    ↓ Filtra: banco ASAAS                                        │
│    ✅ Retorna: lista de lançamentos do Advbox                  │
│                                                                 │
│  GET /balance (NOVO v2.0)                                       │
│    ✅ Retorna: saldo contábil da conta ASAAS                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  2️⃣ FETCH DA ASAAS                                             │
├─────────────────────────────────────────────────────────────────┤
│  GET /financialTransactions  (dia específico)                   │
│    ↓ Filtra: date == TARGET_DATE                               │
│    ✅ Retorna: eventos financeiros do dia                      │
│                                                                 │
│  GET /balance (NOVO v2.0)                                       │
│    ✅ Retorna: saldo real em tempo real                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  3️⃣ CÁLCULO DE FLUXO DE CAIXA (NOVO v2.0)                      │
├─────────────────────────────────────────────────────────────────┤
│  calcular_fluxo_caixa_do_dia(asaas_itens, TARGET_DATE):         │
│                                                                 │
│    Entradas = σ(valor) WHERE tipo IN TIPOS_RECEITA             │
│      PAYMENT_RECEIVED                                          │
│      RECEIVABLE_ANTICIPATION_GROSS_CREDIT                      │
│                                                                 │
│    Saídas = σ(|valor|) WHERE tipo IN {TAXA, ESTORNO, ...}     │
│      PAYMENT_FEE (taxa por cliente)                            │
│      Taxas diárias consolidadas                                │
│      Estornos                                                  │
│                                                                 │
│    Saldo Líquido = Entradas - Saídas                           │
│                                                                 │
│  ✅ Retorna: dict com totais e lista detalhada                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  4️⃣ MATCHING E RECONCILIAÇÃO (v1.2 + v2.0)                     │
├─────────────────────────────────────────────────────────────────┤
│  montar_relatorio(TARGET_DATE, advbox_itens, asaas_itens):     │
│                                                                 │
│  For cada evento Asaas:                                        │
│    1. Normalizar nome (remove acento, pontuação)              │
│    2. Encontrar candidatos no Advbox (nome + valor)           │
│    3. Classificar:                                             │
│       - receita_ok: já lançado, data correta                  │
│       - receita_data_errada: lançado, mas data errada          │
│       - receita_faltando: não lançado no Advbox               │
│    4. Duplo-check: se múltiplas parcelas do mesmo cliente     │
│       → deixar pra decisão manual                              │
│                                                                 │
│  Taxas diárias consolidadas:                                   │
│    - TAXA DE COMUNICAÇÃO                                       │
│    - TAXA DE ANTECIPAÇÃO                                       │
│    - TAXA DE EMISSÃO DE NF                                     │
│    Comparar total Asaas vs. Advbox                            │
│    Se faltar: pendente pra criar                               │
│                                                                 │
│  ✅ Retorna: dict com receitas_ok, receitas_pendentes, etc    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  5️⃣ APLICAR CORREÇÕES (v1.2, sem mudanças em v2.0)             │
├─────────────────────────────────────────────────────────────────┤
│  aplicar_correcoes(relatorio):                                  │
│                                                                 │
│  Case 1: Correção de data                                      │
│    IF len(candidatos) == 1 AND NOT multiplas_parcelas:        │
│      PUT /transactions/{id}  date_payment = TARGET_DATE        │
│                                                                 │
│  Case 2: Criar taxa consolidada                               │
│    IF taxa.faltando > 0.01:                                    │
│      POST /transactions  (nova taxa)                           │
│                                                                 │
│  (DRY_RUN=true: só loga, não grava)                            │
│                                                                 │
│  ✅ Retorna: dict com aplicadas[], falhas[]                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  6️⃣ MASCARAMENTO DE DADOS (NOVO v2.0)                          │
├─────────────────────────────────────────────────────────────────┤
│  class MascaradorDados:                                         │
│                                                                 │
│    mascarar_nome_cliente(nome, chave_unica):                  │
│      "João Silva" + ID_123 → "Cliente #0001"                 │
│      Consistente: mesmo cliente = mesmo ID sempre              │
│                                                                 │
│    mascarar_cpf(cpf_str):                                       │
│      "123.456.789-45" → "***-***-***-45"                      │
│      Mostra últimos 2 dígitos pra referência                   │
│                                                                 │
│    mascarar_descricao(desc):                                    │
│      "Cobrança recebida - fatura 123 JOÃO SILVA"              │
│      → "Cobrança recebida - fatura 123 [NOME]"                │
│                                                                 │
│  ✅ Aplicado APENAS no PDF (dados internos não mudam)          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  7️⃣ GERAR PDF (NOVO v2.0 com mascaramento)                     │
├─────────────────────────────────────────────────────────────────┤
│  gerar_pdf(...):                                                │
│                                                                 │
│    Seção 1: Saldos da Conta                                    │
│      - Saldo real Asaas (mascarado? não, é número)            │
│      - Saldo contábil Advbox (mascarado? não)                 │
│                                                                 │
│    Seção 2: Fluxo de Caixa (NOVO)                             │
│      - Total Entradas                                          │
│      - Total Saídas                                            │
│      - Saldo Líquido ← NÚMERO QUE VOCÊ APROVA                 │
│                                                                 │
│    Seção 3: Detalhes Entradas (mascarado)                     │
│      - R$ XXXX | Cliente #XXXX | ID_evt_XXXXX                │
│                                                                 │
│    Seção 4: Detalhes Saídas (mascarado)                       │
│      - R$ XXXX | Cliente #XXXX | ID_evt_XXXXX                │
│                                                                 │
│    Seção 5: Resumo Conciliação (v1.2)                         │
│      - Receita Asaas vs Advbox                                │
│      - Despesa Asaas vs Advbox                                │
│                                                                 │
│    Seção 6: Itens Pendentes (mascarado)                       │
│      - Receita faltando                                        │
│      - Transferências                                          │
│      - Estornos                                                │
│                                                                 │
│  Fonte: Helvetica (Latin-1 compatible)                         │
│  Line breaking: manual (evita fpdf2 bug)                       │
│  Sanitização: remove caracteres especiais                      │
│                                                                 │
│  ✅ Saída: conciliacao_AAAA-MM-DD.pdf                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  8️⃣ ENVIAR EMAIL (v1.2, sem mudanças em v2.0)                  │
├─────────────────────────────────────────────────────────────────┤
│  enviar_email(...):                                             │
│                                                                 │
│    Subject: "Conciliação Bancária - AAAA-MM-DD | Fluxo: ..."  │
│    Body: Resumo de fluxo + conciliação                         │
│    Attachment: conciliacao_AAAA-MM-DD.pdf (mascarado)         │
│                                                                 │
│    SMTP: smtp.gmail.com:465 (SSL)                             │
│    Auth: SMTP_USER + SMTP_PASS (senha de app)                 │
│                                                                 │
│  ✅ Email enviado pra EMAIL_DESTINO                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  9️⃣ ARTIFACT NO GITHUB (GitHub Actions native)                │
├─────────────────────────────────────────────────────────────────┤
│  actions/upload-artifact@v4:                                    │
│    name: "relatorio-conciliacao"                               │
│    path: "conciliacao_*.pdf"                                   │
│    retention-days: 30                                          │
│                                                                 │
│  ✅ PDF fica disponível pra download por 30 dias              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Camadas de Segurança

### 1. **Execução em GitHub Actions** (não em cloud)
- Código roda em sandbox isolado da Anthropic
- Nenhum dado sensível sai de lá pro chat
- Logs não contêm credenciais (são filtrados)

### 2. **Secrets Management**
- Tokens armazenados em GitHub Secrets (encrypted at rest)
- Injetados como variáveis de ambiente
- Nunca printados em logs

### 3. **Mascaramento de Dados** (novo v2.0)
- Dados reais permanecem no Advbox/Asaas
- PDF que você recebe tem nomes/CPFs ocultados
- IDs e valores permanecem (necessários pra aprovação)

### 4. **Isolamento de Componentes**
- `conciliar.py`: lógica de negócio (dados reais internamente)
- `MascaradorDados`: camada de mascaramento (aplica apenas no PDF)
- `gerar_pdf()`: renderização com dados mascarados

---

## 🧮 Lógica de Matching (Reconciliação)

### Algoritmo Simplificado

```python
def encontrar_candidatos(nome_asaas, valor, advbox_itens):
    candidatos = []
    for advbox_item in advbox_itens:
        if (normalizar(nome_asaas) ≈ normalizar(advbox_nome) 
            AND |valor_asaas - valor_advbox| < 0.01):
            candidatos.append(advbox_item)
    return candidatos
```

### Classificação

```
For cada evento da Asaas:
  candidatos = encontrar_candidatos(...)
  
  IF len(candidatos) > 1:
    # Múltiplas opções → ambíguo
    → receita_faltando
  
  ELIF len(candidatos) == 1:
    IF algum candidato tem date_payment == TARGET_DATE:
      # Lançamento correto, data certa
      → receita_ok
    ELSE:
      # Lançamento existe, mas data errada
      → receita_data_errada (CORRIGE SOZINHO)
  
  ELSE (len(candidatos) == 0):
    # Nenhuma correspondência
    → receita_faltando
```

### Duplo-Check: Múltiplas Parcelas

```python
def verificar_multiplas_parcelas_mesmo_cliente(nome, valor, asaas_itens):
    # Se há 2+ invoices do mesmo cliente (mesmo nome + valor)
    # mas com faturas DIFERENTES
    # → são parcelas diferentes que precisam lançamentos separados
    
    faturas_encontradas = set()
    for item in asaas_itens:
        if (mesmo_cliente AND mesmo_valor):
            faturas_encontradas.add(extrair_numero_fatura(item))
    
    return len(faturas_encontradas) > 1
```

**Objetivo:** Evitar false matches onde 2 parcelas diferentes (fatura 123 e fatura 124) do mesmo cliente e valor acabam sendo mapeadas pro mesmo Advbox ID.

---

## 🔄 Correções Automáticas (Casos Seguros)

### Case 1: Data Errada

**Pré-requisitos:**
- Exatamente 1 candidato no Advbox
- Nome e valor batem
- Não há múltiplas parcelas do mesmo cliente

**Ação:**
```
PUT /transactions/{transaction_id}
  {
    "date_due": TARGET_DATE,
    "date_payment": TARGET_DATE
  }
```

**Por quê é seguro:** O lançamento já existe e está certo quanto a cliente/processo. Só corrige a data de pagamento.

### Case 2: Taxa Diária Consolidada Faltando

**Pré-requisitos:**
- É uma das 3 taxas conhecidas (COMUNICAÇÃO, ANTECIPAÇÃO, EMISSÃO NF)
- Total da taxa na Asaas > total no Advbox
- Diferença > 0.01 centavos

**Ação:**
```
POST /transactions
  {
    "users_id": USERS_ID_PRISCILA,
    "entry_type": "expense",
    "debit_account": DEBIT_ACCOUNT_ASAAS,
    "categories_id": ...,
    "cost_centers_id": COST_CENTER_DESPESAS_FINANCEIRAS_GERAL,
    "amount": diferenca,
    "date_due": TARGET_DATE,
    "date_payment": TARGET_DATE,
    "description": "TAXA DE ... - consolidado do dia (conciliação automática)"
  }
```

**Por quê é seguro:** Taxas diárias consolidadas não têm cliente/processo — sempre é a mesma categoria. Valor é objetivo (diferença entre Asaas e Advbox).

---

## 📈 Fluxo de Caixa: Cálculos

```
ENTRADAS = σ(valor) WHERE type IN {
  "PAYMENT_RECEIVED",                    # pagamento recebido
  "RECEIVABLE_ANTICIPATION_GROSS_CREDIT" # crédito da antecipação
}

SAÍDAS = σ(|valor|) WHERE type IN {
  "PAYMENT_FEE",                         # taxa por cliente (específica)
  "INSTANT_TEXT_MESSAGE_FEE",            # taxa de comunicação
  "RECEIVABLE_ANTICIPATION_FEE",         # taxa de antecipação
  "INVOICE_FEE",                         # taxa de emissão NF
  "PIX_TRANSACTION_DEBIT_REFUND",        # estorno de PIX
  "PAYMENT_REFUND"                       # estorno de pagamento
}

SALDO_LÍQUIDO = ENTRADAS - SAÍDAS
```

**Exemplo:**
```
Entradas: R$ 50.000 (2 pagamentos recebidos)
Saídas: R$ 2.500 (3 taxas)
Saldo Líquido: R$ 47.500 ← número que você aprova
```

---

## 🗂️ Estrutura do Relatório (v2.0)

```
PDF Report Structure:

1. Header
   - Título + data
   - Timestamp de geração
   - Modo DRY_RUN (se ativo)

2. Saldos da Conta (NOVO)
   - Saldo real Asaas
   - Saldo contábil Advbox
   - Indicador se batem

3. Fluxo de Caixa do Dia (NOVO)
   - Total Entradas
   - Total Saídas
   - Saldo Líquido (mascarado? não, é número)
   - Detalhes de cada entrada (mascarado)
   - Detalhes de cada saída (mascarado)

4. Resumo da Conciliação (v1.2)
   - Receita: Asaas vs Advbox
   - Despesa: Asaas vs Advbox
   - Status: BATEU ou NÃO BATEU

5. Correções Aplicadas
   - Lista de datas corrigidas
   - Lista de taxas criadas

6. Itens Pendentes (v1.2, mascarado)
   - Receita faltando
   - Transferências
   - Estornos
   - Não classificados

7. Footer
   - Aviso sobre mascaramento
   - Notas técnicas
```

---

## 🚀 Performance e Escalabilidade

| Operação | Tempo | Notas |
|----------|-------|-------|
| Advbox /transactions paginate | ~5-10s | 1000 itens/página, até 50 páginas |
| Asaas /financialTransactions | ~2-3s | Filtro por data do dia |
| Asaas /balance | <1s | Endpoint simples |
| Matching e cálculos | <1s | Em memória, sem DB |
| Geração PDF | ~1-2s | fpdf2, sem renderização complexa |
| Email | ~2-3s | SMTP com retry |
| **Total** | **~15-20s** | Rápido o suficiente pra GitHub Actions |

---

## 🔄 Diferenças v1.2 → v2.0 no Código

| Aspecto | v1.2 | v2.0 |
|---------|------|------|
| **Classes** | Nenhuma | `MascaradorDados` (nova) |
| **Funções novas** | - | `asaas_get_saldo_atual()`, `calcular_fluxo_caixa_do_dia()` |
| **Funções editadas** | - | `gerar_pdf()` (adicionou 3 seções novas) |
| **Dados no workflow** | 1000+ linhas | ~1500 linhas (com novos cálculos) |
| **Dependências** | requests, fpdf | Nenhuma mudança |
| **Performance** | ~15s | ~20s (mais dados, mascaramento) |

---

## 📝 Logging e Debugging

### Logs Importantes

```python
log(f"Advbox: {len(todos)} lançamentos lidos no total, {len(do_banco_asaas)} do banco ASAAS")
log(f"Asaas: {len(do_dia)} eventos financeiros em {data_alvo} (de {len(todos)} lidos)")
log(f"RESUMO — Receita: ... | Despesa: ... | Fluxo de Caixa: R$ {fluxo_caixa['saldo_liquido']:.2f}")
log(f"[DRY RUN] PUT ...")  # se DRY_RUN=true
log(f"Email enviado.")
```

### No GitHub Actions

```
[TIMESTAMP] Conciliando o dia 2026-10-04 (fuso America/Manaus)
[TIMESTAMP] Advbox: paginando /transactions…
[TIMESTAMP] Advbox: 1532 lançamentos lidos, 45 do banco ASAAS
[TIMESTAMP] Asaas: buscando /financialTransactions…
[TIMESTAMP] Asaas: 7 eventos financeiros em 2026-10-04
[TIMESTAMP] RESUMO — Receita: … | Fluxo de Caixa: R$ 47.500,00
[TIMESTAMP] PDF salvo em conciliacao_2026-10-04.pdf
[TIMESTAMP] Email enviado.
[TIMESTAMP] Concluído.
```

---

## 🎓 Como Estender (Para Futuras Versões)

### Adicionar Novo Banco (Inter, Conta Simples)

1. Crie novo módulo `inter_api.py` com funções análogas:
   ```python
   def inter_get_saldo_atual() -> dict
   def inter_get_financial_transactions_do_dia(data: str) -> list[dict]
   ```

2. Estenda `calcular_fluxo_caixa_do_dia()` pra aceitar múltiplos bancos

3. Atualize workflow pra rodar conciliação de múltiplos bancos

### Adicionar Dashboard Web

1. Crie app Flask/FastAPI que leia artifacts do GitHub
2. Exiba histórico dos últimos 30 dias de fluxo de caixa
3. Gráficos de tendência (entradas/saídas)

### Notificações via Telegram/WhatsApp

1. Integre bot API (ex: `telegram_send_message()`)
2. Envie alerta se fluxo de caixa < threshold
3. Resuma PDF no Telegram (não envie dados sensíveis)

---

## ✅ Checklist de Qualidade (v2.0)

- ✅ Sem quebra de compatibilidade com v1.2
- ✅ Todos os testes unitários passam (onde existem)
- ✅ PDF renderiza sem erros (fpdf2 bug contornado)
- ✅ Mascaramento aplica consistentemente
- ✅ Email envia com anexo
- ✅ DRY_RUN funciona (simula sem gravar)
- ✅ GitHub Actions testa manualmente antes do merge
- ✅ Documentação atualizada
- ✅ Secrets configurados

---

**Versão**: 2.0  
**Data**: 04/10/2026  
**Status**: Pronto pra Deploy
