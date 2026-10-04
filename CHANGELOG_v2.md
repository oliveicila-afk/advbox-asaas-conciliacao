# Changelog — Conciliação Bancária v2.0

## 🎯 Resumo das Mudanças

A v2.0 estende a v1.2 com **Fluxo de Caixa**, **Comparação de Saldos** e **Mascaramento de Dados Sensíveis**. O agente continua rodando no GitHub Actions (seguro), mas agora também monitora movimentações diárias de dinheiro e protege dados sensíveis no relatório.

---

## ✨ Novas Funcionalidades

### 1. **Fluxo de Caixa do Dia** 
- Agregação automática de **entradas** (recebimentos da Asaas) e **saídas** (despesas, taxas, estornos)
- Cálculo do **saldo líquido diário** (entradas - saídas)
- Listagem detalhada de cada movimentação com ID único

**Por quê?** Você acompanha a saúde de caixa em tempo real. Se entrou R$ 100k e saiu R$ 80k, o saldo líquido é +R$ 20k — decisivo pra planejamento de caixa.

### 2. **Comparação de Saldos**
- Fetch do **saldo real em tempo real** da Asaas (via API `/balance`)
- Comparação com **saldo contábil** do Advbox
- Divergência detectada e reportada no PDF

**Por quê?** Saldo do banco ≠ saldo contábil às vezes. A v2.0 mostra ambos pra você ver se há defasagem ou erro de lançamento.

### 3. **Mascaramento de Dados Sensíveis**
- Nomes de clientes: substituídos por `Cliente #XXXX` (ID mascarado mas consistente)
- CPFs: substituídos por `***-***-***-XX` (mostra só últimos 2 dígitos)
- Descrições sensíveis: sanitizadas mas nomes de processo (CNJ) mantidos
- **Valores de transações e IDs permanecem visíveis** (essenciais pra conciliação)

**Por quê?** Você aprova o relatório por números/IDs sem expor dados bancários a terceiros. Seguro pra compartilhar.

---

## 📋 Como Usar

### Instalação

1. **Faça backup da v1.2** (se quiser comparar depois):
   ```bash
   cp conciliar.py conciliar_v1.2.py
   ```

2. **Copie a v2.0**:
   ```bash
   cp conciliar_v2.py conciliar.py
   ```

3. **Atualize o horário de execução** (se quiser):
   - O workflow agora roda às **01:00 da manhã em Manaus** (5 AM UTC)
   - Se preferir outro horário, edite `.github/workflows/conciliacao-diaria.yml` e altere o cron

4. **Dependências**: sem mudanças de v1.2 (mesmas do `requirements.txt`)

### Execução Manual (Teste)

```bash
# Via GitHub Actions (com DRY_RUN=true por padrão)
# Acesse: https://github.com/seu-user/advbox-asaas-conciliacao/actions
# → Clique em "Conciliação diária Advbox x Asaas"
# → "Run workflow" → escolha data e DRY_RUN

# Ou localmente (com arquivo .env configurado):
export ADVBOX_TOKEN="..."
export ASAAS_TOKEN="..."
export SMTP_USER="..."
export SMTP_PASS="..."
export EMAIL_DESTINO="seu-email@..."
export TARGET_DATE="2026-10-04"
export DRY_RUN="false"  # só se quiser gravar de verdade
python conciliar.py
```

---

## 📊 Novo Formato do PDF

O relatório agora mostra, em ordem:

1. **Saldos da Conta** (novo)
   - Saldo real em tempo real da Asaas
   - Saldo contábil do Advbox
   - Útil pra detectar defasagens

2. **Fluxo de Caixa do Dia** (novo)
   - Total de Entradas (recebimentos)
   - Total de Saídas (despesas/taxas)
   - **Saldo Líquido** (o número que você aprova)

3. **Detalhes das Entradas** (novo, mascarado)
   - Cada recebimento com ID, valor, cliente mascarado

4. **Detalhes das Saídas** (novo, mascarado)
   - Cada despesa com ID, valor, descrição

5. **Resumo da Conciliação** (v1.2, sem mudanças)
   - Receita/Despesa Asaas vs. Advbox
   - O que bateu e o que não bateu

6. **Itens que Ficam Pendentes** (v1.2, mascarado)
   - Receita faltando, transferências, estornos
   - Nomes/CPFs mascarados, IDs visíveis

---

## 🔐 Segurança — Como Funciona o Mascaramento

### O que é protegido?
- ❌ **Nomes de clientes**: substituídos por ID numérico (ex: `Cliente #1234`)
- ❌ **CPFs**: mostrados parcialmente (ex: `***-***-***-45`)
- ❌ **Descrições sensíveis**: nomes em CAPS removidos
- ✅ **Mantido visível**: valores, IDs de transação, números de processo (CNJ)

### Por quê?
Você pode compartilhar o PDF com contador/auditor sem expor dados bancários pessoais. O aprovador ainda vê tudo que precisa (IDs, valores, datas) pra tomar decisão.

### Internamente?
Nenhuma mudança. Dados internos (lógica de matching, correções) ainda usam dados reais. O mascaramento é **apenas pra PDF** — não afeta cálculos.

---

## 🚀 Roadmap — O que Vem Depois

Para as próximas versões:

1. **v2.1**: Suporte para **Inter Bank** (além de Asaas)
2. **v2.2**: Suporte para **Conta Simples** (além de Asaas + Inter)
3. **v2.3**: Dashboard web pra visualizar histórico de fluxo de caixa (últimos 30 dias, por exemplo)
4. **v3.0**: Integração com **Telegram/WhatsApp** pra notificações automáticas (fluxo de caixa crítico, etc)

---

## ❓ Perguntas Frequentes

### 1. **Posso usar v2.0 e v1.2 ao mesmo tempo?**
Sim! Mantenha `conciliar.py` como v2.0 (padrão) e `conciliar_v1.2.py` de backup se precisar comparar.

### 2. **E se a Asaas não devolver o saldo?**
A v2.0 log a falha, mas não interrompe a execução. O PDF vai mostrar "Não foi possível obter saldo". Resto do relatório funciona normal.

### 3. **CPF aparecer no relatório?**
Todas as mudanças de v1.2 → v2.0 incluem mascaramento. Se algum CPF aparecer, é bug — abra uma issue.

### 4. **Mas e se eu quiser ver o nome real do cliente?**
O ID mascarado (ex: `Cliente #1234`) é **consistente** — sempre o mesmo cliente recebe o mesmo ID. Você pode manter uma tabela externa CPF/ID pra desmascarar se precisar.

### 5. **Vale a pena migrar de v1.2 pra v2.0?**
- Se você quer **monitorar fluxo de caixa**: sim, definitivamente
- Se você compartilha o PDF com terceiros: sim, mascaramento é valor agregado
- Se você só quer conciliação de lançamentos: v1.2 já faz isso, mas v2.0 não quebra nada

---

## 📦 Arquivos Modificados

```
.github/workflows/conciliacao-diaria.yml  (horário: 07 → 05 UTC = 03 → 01 Manaus)
conciliar.py  (nova versão: v2.0, estendida de v1.2)
CHANGELOG_v2.md  (este arquivo — novo)
```

Mantém compatibilidade com:
```
requirements.txt  (sem mudanças)
.gitignore  (sem mudanças)
analise_*.json  (dados de teste — sem mudanças)
```

---

## 🔧 Troubleshooting

| Problema | Causa | Solução |
|----------|-------|--------|
| `ImportError: No module named 'requests'` | Dependências não instaladas | `pip install -r requirements.txt` |
| `ADVBOX_TOKEN/ASAAS_TOKEN não configurados` | Secrets não setados no GitHub | Vá em Settings → Secrets and variables → Actions → crie os secrets |
| PDF gerado mas com "Não foi possível..." | API da Asaas/Advbox indisponível | Tente rodar novamente em alguns minutos |
| Nenhuma mudança no Advbox (DRY_RUN) | Modo DRY_RUN ativo | Na workflow, desmarque `dry_run` ou passe `DRY_RUN=false` |

---

## 📞 Contato / Sugestões

Encontrou um bug ou tem sugestão? Abra uma **issue** neste repositório com:
- O que esperava
- O que viu no PDF/log
- Prints do erro (sem expor dados sensíveis!)

---

**Versão**: 2.0  
**Último update**: 04/10/2026  
**Mantido por**: Equipe de Automação Financeira
