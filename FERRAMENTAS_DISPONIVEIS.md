# 🛠️ Ferramentas Disponíveis para Investigação

Uma visão completa de todos os scripts e workflows criados para investigar as divergências.

---

## 📁 Scripts de Análise

### 1. **auditoria_10_dias.py** ✅ PRINCIPAL
**Propósito**: Auditoria rápida dos 10 primeiros dias de setembro
**Requer**: Tokens de API (ADVBOX_TOKEN, ASAAS_TOKEN)
**Saída**: Resumo de 1 linha por dia (Match/Divergência + valores)

```bash
python3 auditoria_10_dias.py
```

**Exemplo de output**:
```
✓ 2026-09-05: REC    500.00=   500.00 | DESP    100.00=   100.00
✗ 2026-09-08: REC   1000.00=  1000.00 | DESP   5000.00!=  2000.00
```

**Melhor para**: Visão geral rápida dos 10 dias

---

### 2. **diagnostico_transacoes_dia.py** ✅ DETALHADO
**Propósito**: Análise linha por linha de um dia específico
**Requer**: Tokens de API (ADVBOX_TOKEN, ASAAS_TOKEN)
**Saída**: Lista completa de receitas e despesas com IDs

```bash
# Ver setembro 8
DIA_ALVO="2026-09-08" python3 diagnostico_transacoes_dia.py

# Ver setembro 4
DIA_ALVO="2026-09-04" python3 diagnostico_transacoes_dia.py
```

**Melhor para**: Entender transações específicas de um dia

---

### 3. **debug_advbox_completo.py** 🔍 DEBUG
**Propósito**: Verificar estrutura de dados do Advbox
**Requer**: Tokens de API (ADVBOX_TOKEN)
**Saída**: Tipos de transações e totais por tipo para um dia

```bash
python3 debug_advbox_completo.py
```

**Melhor para**: Verificar se dados estão sendo retornados corretamente

---

### 4. **debug_advbox_raw.py** 🔍 DEBUG
**Propósito**: Ver estrutura bruta de um objeto Advbox
**Requer**: Tokens de API (ADVBOX_TOKEN)
**Saída**: Primeiras 5 transações completas com todos os campos

```bash
python3 debug_advbox_raw.py
```

**Melhor para**: Entender quais campos estão disponíveis

---

## 💾 Scripts de Cache (SEM tokens necessários)

### 5. **cache_transactions.py** 📥 CACHE
**Propósito**: Baixar e salvar dados de API em JSON
**Requer**: Tokens de API (ADVBOX_TOKEN, ASAAS_TOKEN)
**Saída**: `transactions_cache.json` (~5MB)

```bash
python3 cache_transactions.py
```

**Resultado**: Arquivo JSON com toda estrutura de dados

---

### 6. **diagnostico_transacoes_offline.py** 📊 ANÁLISE OFFLINE
**Propósito**: Mesma análise que #2, mas usando cache em vez de API
**Requer**: `transactions_cache.json` (criado pelo #5)
**Saída**: Igual a #2

```bash
# Com cache local
DIA_ALVO="2026-09-08" python3 diagnostico_transacoes_offline.py

# Com cache de outro lugar
CACHE_FILE="/path/to/cache.json" DIA_ALVO="2026-09-08" python3 diagnostico_transacoes_offline.py
```

**Melhor para**: Análise detalhada DEPOIS de ter dados em cache

---

### 7. **analise_matching_manual.py** 🔗 MATCHING
**Propósito**: Matching inteligente entre transações Asaas e Advbox
**Requer**: `transactions_cache.json`
**Saída**: Detalhes de quais transações combinam e quais não combinam

```bash
DIA_ALVO="2026-09-08" python3 analise_matching_manual.py
```

**Exemplo de output**:
```
✓ 1. [95%] Asaas R$    150.00 = Advbox R$    150.00
   Asaas:  Pagamento PIX para Fulano
   Advbox: PIX - Fulano

SEM MATCH EM ADVBOX (3 itens):
1. R$  11,133.35 | TRANSFER
   PIX - ELIZETH SOUZA DA CRUZ DE MELO
```

**Melhor para**: Identificar transações sem match e entender por quê

---

## 🤖 GitHub Actions Workflows

### 8. **auditoria-10-dias.yml** 📋 CI/CD
**Arquivo**: `.github/workflows/auditoria-10-dias.yml`
**Propósito**: Rodar auditoria dos 10 dias automaticamente
**Trigger**: Manual (Actions → Run workflow)
**Saída**: Log no GitHub Actions

```yaml
# Acesse: GitHub Actions → "Auditoria - Primeiros 10 dias"
# Clique: "Run workflow"
# Aguarde: 2-3 minutos
```

---

### 9. **diagnostico-dia.yml** 🎯 CI/CD PARAMETRIZADO
**Arquivo**: `.github/workflows/diagnostico-dia.yml`
**Propósito**: Análise de um dia específico via GitHub Actions
**Trigger**: Manual com parâmetro de data
**Saída**: Log detalhado no GitHub Actions

```yaml
# Acesse: GitHub Actions → "Diagnóstico - Transações de um dia específico"
# Clique: "Run workflow"
# Preencha:
#   dia: "2026-09-08"
# Aguarde: 2-3 minutos
# Resultado: Output mostra todas as transações do dia
```

**Melhor para**: Diagnóstico sem precisar de setup local

---

### 10. **cache-e-diagnostico.yml** 🔄 CI/CD COMPLETO
**Arquivo**: `.github/workflows/cache-e-diagnostico.yml`
**Propósito**: Atualizar cache + rodar diagnóstico
**Trigger**: Manual com 2 parâmetros
**Saída**: Cache compartilhável + Diagnóstico

```yaml
# Acesse: GitHub Actions → "Cache de Dados + Diagnóstico Offline"
# Clique: "Run workflow"
# Preencha:
#   atualizar_cache: "sim"
#   dia_diagnostico: "2026-09-08"
# Aguarde: 3-5 minutos
# Resultado: 
#   1. Output mostra diagnóstico
#   2. Artefato 'transactions-cache' fica disponível para download
```

**Melhor para**: Gerar cache + analisar em uma única execução

---

## 📋 Documentos de Referência

### **ANALISE_DIVERGENCIAS.md**
Análise estruturada com:
- Status dos 10 dias
- Resumo das divergências por dia
- Hipóteses testadas
- Próximos passos

### **PROXIMO_PASSO.md**
Guia passo a passo:
- Como usar GitHub Actions
- Como fazer análise profunda
- Questão chave para o usuário
- Checklist

### **FERRAMENTAS_DISPONIVEIS.md** (este arquivo)
Catálogo completo de todas as ferramentas

---

## 🚀 Fluxo Recomendado para Investigação

### **Fase 1: Visão Geral Rápida** (5 min)
```bash
# Se tiver tokens locais:
python3 auditoria_10_dias.py

# Se não, usar GitHub Actions:
# Actions → "Auditoria - Primeiros 10 dias" → Run
```

### **Fase 2: Gerar Cache** (5-10 min)
```bash
# Via GitHub Actions (recomendado):
# Actions → "Cache de Dados + Diagnóstico Offline"
#   atualizar_cache: "sim"
#   dia_diagnostico: "2026-09-04"
```

### **Fase 3: Análise Detalhada** (offline, sem tokens)
```bash
# Com cache em mãos:
DIA_ALVO="2026-09-08" python3 diagnostico_transacoes_offline.py
DIA_ALVO="2026-09-08" python3 analise_matching_manual.py
```

### **Fase 4: Investigação Específica** (conforme necessário)
```bash
# Se problema for de mapeamento de tipos:
python3 -c "..."  # Ver "AÇÃO 3" no PROXIMO_PASSO.md

# Se problema for de transações específicas:
# Usar matching manual (#7) para verificar quais não combinam
```

---

## 🎯 Qual Ferramenta Usar?

| Pergunta | Ferramenta |
|----------|-----------|
| Todos os 10 dias batem? | `auditoria_10_dias.py` ou workflow #9 |
| O que está diferente em um dia? | `diagnostico_transacoes_dia.py` ou #6 |
| Quais transações não têm match? | `analise_matching_manual.py` |
| Estou sem tokens, como faço? | GitHub Actions #10 para gerar cache |
| Tenho cache, como analiso offline? | `diagnostico_transacoes_offline.py` ou #7 |

---

## 🔑 Variáveis de Ambiente

```bash
# Obrigatorias para scripts com API
export ADVBOX_TOKEN="seu_token_advbox"
export ASAAS_TOKEN="seu_token_asaas"

# Opcionais
export TIMEZONE="America/Manaus"  # Padrão
export DIA_ALVO="2026-09-08"      # Padrão: último dia com divergência
export CACHE_FILE="transactions_cache.json"  # Padrão
```

---

## 📊 Exemplos de Uso Prático

### Investigar por que setembro 8 tem divergência de R$ 78,758.92

```bash
# Opção 1: Com GitHub Actions
# 1. GitHub Actions → "Cache de Dados + Diagnóstico Offline"
# 2. Parâmetros: atualizar_cache=sim, dia_diagnostico=2026-09-08
# 3. Aguarde conclusão
# 4. Veja output e artefato

# Opção 2: Local (com tokens)
# 1. python3 auditoria_10_dias.py  (ver status geral)
# 2. DIA_ALVO="2026-09-08" python3 diagnostico_transacoes_dia.py  (ver detalhes)
# 3. Analisar transações de tipo TRANSFER

# Opção 3: Offline (com cache prévio)
# 1. Ter transactions_cache.json
# 2. DIA_ALVO="2026-09-08" python3 analise_matching_manual.py
# 3. Ver quais transações TRANSFER não têm match em Advbox
```

---

## 💡 Dicas

- **Sempre comece pela auditoria geral** para ver quais dias têm problema
- **Cache é seu amigo** quando precisa de análise profunda
- **Matching manual revela tudo** - mostra exatamente quais transações faltam
- **GitHub Actions é mais rápido** quando você não tem tokens locais
- **Documente seus achados** em um arquivo novo para referência futura

---

**Status**: Ferramentas completamente implementadas e documentadas
**Tempo de investigação típico**: 30 min para um dia completo (com cache)
