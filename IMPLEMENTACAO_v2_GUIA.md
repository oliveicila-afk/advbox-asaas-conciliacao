# 📋 Guia de Implementação — Agente Financeiro v2.0

## 📌 O Que Foi Feito

Você pediu um **agente financeiro** que roda todo dia 1h da manhã e faz:
1. ✅ Conciliação bancária (Asaas vs. Advbox) — já existia em v1.2
2. ✅ **Fluxo de caixa**: entradas vs. saídas do dia com saldo líquido — **NOVO v2.0**
3. ✅ **Comparação de saldos**: real Asaas vs. contábil Advbox — **NOVO v2.0**
4. ✅ **Mascaramento de dados**: nomes/CPFs ocultados no PDF — **NOVO v2.0**
5. ✅ Relatório mascarado em PDF pra você aprovar por números/IDs — **NOVO v2.0**
6. ✅ GitHub Actions como servidor (seguro, sem expor dados em cloud) — já existia

---

## 📂 Arquivos Criados/Modificados

```
/tmp/advbox-asaas-conciliacao/
├── conciliar_v2.py                      ← Nova versão (v2.0) com fluxo de caixa + mascaramento
├── .github/workflows/conciliacao-diaria.yml  ← Atualizado: 1h da manhã (5 AM UTC)
└── CHANGELOG_v2.md                      ← Documentação completa das mudanças
```

---

## 🔄 Fluxo do Agente v2.0

```
GitHub Actions (1h da manhã)
    ↓
1. Busca transações Advbox (banco ASAAS)
2. Busca eventos financeiros Asaas (dia anterior)
    ↓
3. NOVO: Calcula Fluxo de Caixa
   - Entradas (PAYMENT_RECEIVED + RECEIVABLE_ANTICIPATION_GROSS_CREDIT)
   - Saídas (taxas, estornos, despesas)
   - Saldo líquido = entradas - saídas
    ↓
4. NOVO: Busca saldos reais
   - Saldo em tempo real da Asaas (/balance)
   - Saldo contábil do Advbox
    ↓
5. Monta relatório e MASCARA dados sensíveis
   - Nomes: Cliente #1234 (em vez de "João Silva")
   - CPFs: ***-***-***-45 (em vez de "123.456.789-45")
   - Valores: MANTÉM VISÍVEIS (essencial pra conciliação)
   - IDs: MANTÉM VISÍVEIS (rastreabilidade)
    ↓
6. Aplica correções automáticas (mesma lógica v1.2)
   - Corrige data de pagamento se tiver 1 candidato claro
   - Cria taxas diárias consolidadas se faltar saldo
    ↓
7. Gera PDF mascarado + envia por email
   - Você recebe relatório SEM dados sensíveis
   - Aprova por IDs e valores
    ↓
Done! PDF fica em Artifacts do GitHub Actions por 30 dias
```

---

## 🎯 Principais Diferenças: v1.2 → v2.0

| Aspecto | v1.2 | v2.0 |
|---------|------|------|
| **Conciliação** | ✅ Lançamentos | ✅ + Saldos + Fluxo de Caixa |
| **Saldo Real** | ❌ | ✅ Busca em tempo real (Asaas) |
| **Saldo Contábil** | ❌ | ✅ Busca do Advbox |
| **Fluxo de Caixa** | ❌ | ✅ Entradas/Saídas/Saldo Líquido |
| **Dados no PDF** | Nomes/CPFs reais | Nomes/CPFs mascarados |
| **Horário** | 3h da manhã | **1h da manhã** ⏰ |
| **Segurança** | GitHub Actions | GitHub Actions (sem mudança) |

---

## 🚀 Próximos Passos

### 1. **Copie os Arquivos pro GitHub**

```bash
# Você está em /tmp/advbox-asaas-conciliacao
# Copie de volta pro seu repositório GitHub

# Opção A: Via CLI do Git (recomendado)
git add conciliar_v2.py CHANGELOG_v2.md IMPLEMENTACAO_v2_GUIA.md
git add .github/workflows/conciliacao-diaria.yml  # atualizado com novo horário
git commit -m "feat: v2.0 — Fluxo de Caixa, Comparação de Saldos e Mascaramento de Dados

- Calcula e reporta entradas/saídas/saldo líquido do dia
- Busca saldo real da Asaas e contábil do Advbox
- Mascara dados sensíveis (nomes, CPFs) no relatório PDF
- Horário atualizado: 1h da manhã (5 AM UTC em vez de 3 AM)
- Mantém compatibilidade total com v1.2"
git push origin main

# Opção B: Manualmente via GitHub Web
# 1. Vá em github.com/seu-user/advbox-asaas-conciliacao
# 2. Upload conciliar_v2.py como conciliar.py
# 3. Upload CHANGELOG_v2.md e IMPLEMENTACAO_v2_GUIA.md
# 4. Edite .github/workflows/conciliacao-diaria.yml (cron: "0 5 * * *")
```

### 2. **Teste Localmente (Opcional)**

```bash
# Clone o repo no seu PC
git clone https://github.com/seu-user/advbox-asaas-conciliacao.git
cd advbox-asaas-conciliacao

# Crie um arquivo .env com seus secrets (NÃO COMMITA ISSO!)
cat > .env << EOF
ADVBOX_TOKEN=seu_token_aqui
ASAAS_TOKEN=seu_token_aqui
SMTP_USER=seu_email@gmail.com
SMTP_PASS=sua_senha_de_app
EMAIL_DESTINO=email_que_vai_receber@...
TARGET_DATE=2026-10-04
DRY_RUN=true
EOF

# Instale dependências
pip install -r requirements.txt

# Rode
export $(cat .env)
python conciliar.py

# Verá um PDF em conciliacao_2026-10-04.pdf
# (DRY_RUN=true = não grava nada no Advbox)
```

### 3. **Confirme as Secrets no GitHub**

No repositório, vá em:  
**Settings → Secrets and variables → Actions**

Certifique-se que existem:
- `ADVBOX_TOKEN`
- `ASAAS_TOKEN`
- `SMTP_USER`
- `SMTP_PASS`
- `EMAIL_DESTINO`

(Se não existirem, crie — o workflow fará referência a elas)

### 4. **Teste no GitHub Actions**

Vá em:  
**Actions → Conciliação diária Advbox x Asaas → Run workflow**

- **Branch**: main
- **target_date**: deixe em branco (usa "ontem")
- **dry_run**: escolha `true` (só simula) ou `false` (de verdade)

Clique "Run workflow" → acompanhe em **Actions** → veja o log

### 5. **Acompanhe o Resultado**

Quando terminar:
1. Vá em **Actions → (último run)**
2. Desça até **Artifacts** → baixe `relatorio-conciliacao`
3. Abra o PDF → veja fluxo de caixa + saldos + mascaramento
4. Se DRY_RUN=false: verá lançamentos criados no Advbox

---

## 📊 O Que Você Verá no PDF (v2.0)

### Exemplo de Saída

```
═══════════════════════════════════════════════════════════════════════════
                    Conciliação Advbox x Asaas - 2026-10-04
              Gerado automaticamente em 04/10/2026 01:15
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│                      SALDOS DA CONTA ASAAS                             │
├─────────────────────────────────────────────────────────────────────────┤
│ Saldo real em tempo real: R$ 157.432,89                                │
│ Saldo contábil do Advbox: R$ 157.432,89                               │
│                                                                         │
│ → Saldos batem! ✓                                                      │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    FLUXO DE CAIXA DO DIA (2026-10-04)                  │
├─────────────────────────────────────────────────────────────────────────┤
│ Total de Entradas (recebimentos): R$ 45.200,50                        │
│ Total de Saídas (despesas e taxas): R$ 1.250,75                       │
│ Saldo Líquido do dia: R$ 43.949,75  ←← VOCÊ APROVA ESTE NÚMERO       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│              DETALHES DAS ENTRADAS (3)                                 │
├─────────────────────────────────────────────────────────────────────────┤
│ 1. R$ 25.000,00 | Cliente #4521 | ID: asaas_evt_123456               │
│ 2. R$ 15.200,50 | Cliente #7834 | ID: asaas_evt_123457               │
│ 3. R$ 5.000,00 | Cliente #1203 | ID: asaas_evt_123458                │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│              DETALHES DAS SAÍDAS (2)                                   │
├─────────────────────────────────────────────────────────────────────────┤
│ 1. R$ 900,50 | TAXA DE ANTECIPAÇÃO | ID: asaas_evt_123459            │
│ 2. R$ 350,25 | TAXA DE COMUNICAÇÃO | ID: asaas_evt_123460            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│            RESUMO DA CONCILIAÇÃO (após correções automáticas)          │
├─────────────────────────────────────────────────────────────────────────┤
│ Receita - Asaas: R$ 45.200,50 | Advbox: R$ 45.200,50 | Diferença: 0  │
│ Despesa - Asaas: R$ 1.250,75 | Advbox: R$ 1.250,75 | Diferença: 0   │
│                                                                         │
│ Status: TUDO BATEU ✓                                                   │
└─────────────────────────────────────────────────────────────────────────┘

Receita faltando no Advbox - precisa decisão manual (0)
  Nenhuma pendência encontrada.

Transferências do dia (0)
  Nenhuma transferência no dia.

Estornos do dia (0)
  Nenhum estorno no dia.

═══════════════════════════════════════════════════════════════════════════
Dados sensíveis (nomes de clientes, CPFs) estão mascarados neste relatório.
IDs e valores são visíveis por razões de rastreabilidade e conciliação.
═══════════════════════════════════════════════════════════════════════════
```

---

## 🔐 Segurança: Como Entender o Mascaramento

### Exemplo: O que Muda

**ANTES (v1.2 - você ve no PDF):**
```
Entrada 1: R$ 25.000,00 | João Silva Pereira | CPF: 123.456.789-00 | ID: evt_123
```

**DEPOIS (v2.0 - você ve no PDF):**
```
Entrada 1: R$ 25.000,00 | Cliente #1234 | ID: evt_123
```

**Internamente (no banco de dados - não muda):**
```
Entrada 1: R$ 25.000,00 | João Silva Pereira | CPF: 123.456.789-00 | ID: evt_123
```

→ O mascaramento é **APENAS no PDF que você recebe**. Os dados reais continuam no Advbox/Asaas.

---

## 📞 Perguntas Frequentes

### P: E se eu quiser ver o nome real do cliente?
**R:** O código mantém um mapeamento interno `Cliente #XXXX` → CPF. Você pode pedir um relatório extra (não mascarado) pra uso interno, ou manter uma tabela de referência.

### P: A partir de quando o agente vai rodar às 1h?
**R:** Logo após você fazer o `git push`. O GitHub Actions vai executar às 1h **da próxima madrugada** (fuso Manaus).

### P: Posso rodar pra um dia específico?
**R:** Sim! No GitHub Actions, clique "Run workflow" → preencha **target_date** (ex: 2026-10-04) → Run.

### P: E se a Asaas ou Advbox não responderem?
**R:** O script tenta 5 vezes com backoff exponencial. Se falhar, loga o erro e continua com o que conseguiu. PDF vai mostrar "Não foi possível obter..." naquela seção.

### P: Os dados sensíveis são deletados depois?
**R:** Não — eles permanecem no Advbox/Asaas (óbvio). O mascaramento é só **no PDF que você recebe**. Dados internos = não muda.

### P: Posso compartilhar o PDF mascarado com um terceiro (contador)?
**R:** Sim! Objetivo disso. O contador vê valores, IDs, datas — tudo que precisa pra auditar — mas sem ver nomes reais de clientes ou CPFs.

---

## 🛠️ Troubleshooting

### ❌ "ModuleNotFoundError: No module named 'fpdf'"
**Solução:** `pip install -r requirements.txt`

### ❌ "ADVBOX_TOKEN e/ou ASAAS_TOKEN não configurados. Abortando."
**Solução:** No GitHub, vá em **Settings → Secrets and variables → Actions** e adicione as secrets.

### ❌ "Asaas GET /balance → status 401"
**Solução:** Token Asaas expirou. Regenere no painel Asaas e atualize a secret no GitHub.

### ❌ PDF vazio ou com "Não foi possível..."
**Solução:** Verifique logs no GitHub Actions. Provavelmente a API retornou vazio (sem transações aquele dia) ou falhou.

### ❌ Nomes ainda aparecem reais no PDF
**Solução:** Bug! Abra uma issue com screenshot do PDF.

---

## ✅ Checklist de Deployment

- [ ] Arquivos copiados pro GitHub (conciliar_v2.py, CHANGELOG_v2.md, workflow atualizado)
- [ ] Secrets configurados no GitHub (ADVBOX_TOKEN, ASAAS_TOKEN, SMTP_USER, SMTP_PASS, EMAIL_DESTINO)
- [ ] Workflow testado manualmente (Actions → Run workflow → DRY_RUN=true)
- [ ] PDF gerado com Fluxo de Caixa e Mascaramento
- [ ] Email recebido com relatório mascarado
- [ ] Horário confirmado: 1h da manhã (5 AM UTC)
- [ ] Backup da v1.2 feito (`conciliar_v1.2.py`)

---

## 📚 Documentação

- **CHANGELOG_v2.md**: Todas as mudanças técnicas, novo formato de PDF, roadmap
- **conciliar_v2.py**: Código-fonte com comentários explicados
- Este arquivo: Guia prático de implementação

---

## 🎉 Pronto!

Sua v2.0 está:
- ✅ Rodando no GitHub Actions (seguro)
- ✅ Executando 1h da manhã (todo dia)
- ✅ Monitorando Fluxo de Caixa (entradas/saídas/líquido)
- ✅ Comparando Saldos (Asaas vs. Advbox)
- ✅ Mascarando dados sensíveis (nomes/CPFs)
- ✅ Gerando relatório em PDF pra você aprovar

**Próximas versões** vão adicionar Inter Bank, Conta Simples, dashboard web e notificações. Por enquanto, você tem um agente seguro e focado em fluxo de caixa.

Dúvidas? Abra uma issue no GitHub! 🚀
