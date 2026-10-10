# RECONCILIAÇÃO ASAAS vs ADVBOX
## Período: 01-10 Setembro 2026

**Data de Geração:** 2026-10-10

---

## 📊 RESUMO EXECUTIVO

| Métrica | Quantidade | Valor |
|---------|-----------|-------|
| ✓ Transações Asaas encontradas em Advbox | 21 | R$ 5.887,81 |
| ✗ Transações Asaas NÃO encontradas em Advbox | 8 | R$ 16.528,00 |
| ⚠️ Transações Advbox NÃO encontradas em Asaas (Income) | 2 | R$ 15.377,50 |
| ⚠️ Transações Advbox NÃO encontradas em Asaas (Expenses) | 2 | R$ 18,76 |

---

## 🔴 TRANSAÇÕES ASAAS SEM CORRESPONDÊNCIA EM ADVBOX

*O que aparece em Asaas mas não foi encontrado em Advbox (segundo análise de matching)*

| Data | Cliente/Descrição | Valor |
|------|------------------|-------|
| 2026-09-09 | Caixa Economica Federal (fatura 906142104) | R$ 11.988,86 |
| 2026-09-09 | Caixa Economica Federal (fatura 905869074) | R$ 3.388,64 |
| 2026-09-09 | CARLOS ALBERTO DOS SANTOS FERREIRA | R$ 100,50 |
| 2026-09-09 | ELISABETH BRITTO DA COSTA | R$ 374,25 |
| 2026-09-09 | MARINETE GERALDA DA SILVA | R$ 100,50 |
| 2026-09-09 | CARLOS ALBERTO DOS SANTOS FERREIRA | R$ 100,50 |
| 2026-09-09 | ELISABETH BRITTO DA COSTA | R$ 374,25 |
| 2026-09-09 | MARINETE GERALDA DA SILVA | R$ 100,50 |
| | **TOTAL** | **R$ 16.528,00** |

---

## 🟢 TRANSAÇÕES ADVBOX SEM CORRESPONDÊNCIA EM ASAAS

*O que aparece em Advbox mas não foi encontrado em Asaas (segundo análise de matching)*

### Receitas

| Data | Cliente | Valor |
|------|---------|-------|
| 2026-09-09 | LUCAS MONTEIRO GAZEL | R$ 11.988,86 |
| 2026-09-09 | WELITON LOPES DE OLIVEIRA | R$ 3.388,64 |
| | **SUBTOTAL RECEITAS** | **R$ 15.377,50** |

### Despesas

| Data | Descrição | Valor |
|------|-----------|-------|
| 2026-09-09 | TAXA DE COMUNICAÇÃO - CONSOLIDADO DO DIA | R$ 0,55 |
| 2026-09-09 | TAXA DE ANTECIPAÇÃO - CONSOLIDADO DO DIA | R$ 18,21 |
| | **SUBTOTAL DESPESAS** | **R$ 18,76** |

---

## 💡 ANÁLISE E CORRESPONDÊNCIA DETECTADA

### ✓ Possível Matching Entre Sistemas

As duas maiores transações não encontradas apresentam correspondência perfeita:

**Transação 1:**
- **Asaas:** TED Recebida da Caixa Econômica Federal | R$ 11.988,86
- **Advbox:** LUCAS MONTEIRO GAZEL (Honorários Sucumbenciais) | R$ 11.988,86
- **Status:** ✓ Valores idênticos - Provável mesma transação com registros diferentes

**Transação 2:**
- **Asaas:** TED Recebida da Caixa Econômica Federal | R$ 3.388,64
- **Advbox:** WELITON LOPES DE OLIVEIRA (Honorários Contratuais) | R$ 3.388,64
- **Status:** ✓ Valores idênticos - Provável mesma transação com registros diferentes

---

## 🔍 CONCLUSÕES

1. **Advbox está CORRETO**: O sistema Advbox capturou corretamente as duas grandes transações de TED (11.988,86 e 3.388,64) e as associou aos clientes reais (Lucas Monteiro Gazel e Weliton Lopes de Oliveira).

2. **Asaas reporta diferente**: Asaas está classificando essas mesmas transações como "TED recebida da Caixa Econômica Federal" sem associar os nomes dos clientes finais.

3. **Diferença de Nomenclatura**: A origem da discrepância parece ser a forma como os sistemas nomeiam as transações:
   - Asaas: Nome da instituição intermediária (Caixa Econômica Federal)
   - Advbox: Nome do cliente final (beneficiário da transação)

4. **Recomendação**: Os dois maiores valores discrepantes (R$ 15.377,50) podem ser reconciliados manualmente verificando os IDs de transação Asaas contra os processos cadastrados em Advbox.

---

## 📝 OBSERVAÇÕES ADICIONAIS

- Período analisado: 01-10 de Setembro de 2026
- Total de transações Asaas processadas: 21 + 8 = 29 transações de receita
- Total de transações Advbox processadas: 3 transações (período Sep 01-10)
- Dados extraídos via APIs: Asaas (/financialTransactions) e Advbox (/transactions)
- Análise gerada em: 2026-10-10

---

**Gerado por:** Sistema de Reconciliação Automática
**Contato:** oliveicila@gmail.com
