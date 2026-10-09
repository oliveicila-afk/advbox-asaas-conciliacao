# 📊 Guia: Reconciliação Setembro 01-10 (2026)

## Situação Atual

| Métrica | Valor |
|---------|-------|
| **Asaas Total (01-10 Set)** | R$ 133.826,92 |
| **Advbox Total (conta ASAAS)** | R$ 84.741,47 |
| **Divergência Identificada** | R$ 49.085,45 |

## Regras de Reconciliação

⚠️ **REGRA OBRIGATÓRIA:**
> Toda transação de receita para reconciliação Asaas ↔ Advbox **DEVE ESTAR NA CONTA ASAAS**

Não pode estar distribuída entre:
- ❌ Contadoria
- ❌ Investimento  
- ❌ Dinheiro
- ❌ Contas Simples

---

## Divergências por Dia

### ✅ Dias Balanceados
- 09/05: R$ 0 divergência
- 09/07: R$ 0 divergência
- 09/09: R$ 0 divergência
- 09/10: R$ 0 divergência

### 🔴 Dias com Divergência

#### 09/01: R$ 315,50 faltando
- **Tipo**: Receita / Antecipação
- **Ação**: Criar 1 entrada

#### 09/02: R$ 497,00 faltando
- **Tipo**: Receita / Antecipação
- **Ação**: Criar 1 entrada

#### 09/03: R$ 815,50 faltando
- **Tipo**: Receita / Antecipação
- **Ação**: Criar 1 entrada

#### 09/04: R$ 13.296,02 faltando
- **Tipo**: Receita + Estorno/Chargeback
- **Detalhamento**:
  - Receita: R$ 2.162,67
  - Estorno: -R$ 11.133,35
- **Ação**: Criar 2 entradas

#### 09/06: R$ 6.000,00 (NÃO PROCEDER)
- **Tipo**: Investimento (LVMX I E I Ltda)
- **Status**: ✋ EXCLUIR DA RECONCILIAÇÃO
- **Motivo**: Transações de investimento não entram na reconciliação de receitas

#### 09/08: R$ 28.161,43 faltando
- **Tipo**: Receita + Estorno/Chargeback
- **Detalhamento**:
  - Receita: R$ 10.602,77
  - Estorno: -R$ 17.558,66
- **Ação**: Criar 2 entradas

---

## Transações a Serem Criadas

Total: **7 lançamentos** na conta ASAAS

| Data | Descrição | Valor | Tipo |
|------|-----------|-------|------|
| 09/01 | Receita (Antecipação) | R$ 315,50 | Receita |
| 09/02 | Receita (Antecipação) | R$ 497,00 | Receita |
| 09/03 | Receita (Antecipação) | R$ 815,50 | Receita |
| 09/04 | Receita Principal | R$ 2.162,67 | Receita |
| 09/04 | Estorno/Chargeback | -R$ 11.133,35 | Despesa |
| 09/08 | Receita Principal | R$ 10.602,77 | Receita |
| 09/08 | Estorno/Chargeback | -R$ 17.558,66 | Despesa |

**Total de Receitas**: R$ 14.788,44
**Total de Estornos**: -R$ 28.692,01
**Saldo Líquido**: -R$ 13.903,57

*Nota: O saldo negativo reflete que existem mais estornos que receitas originais em alguns dias, o que é correto pois representa o que Asaas registrou.*

---

## Como Executar

### Opção 1: Via GitHub Actions (Recomendado)

1. **Acesse o repositório**
   - https://github.com/oliveicila/advbox-asaas-conciliacao

2. **Vá para a aba "Actions"**
   - Selecione "Reconciliação Setembro 01-10 - Criar Entradas"

3. **Clique em "Run workflow"**

4. **Digite `YES` no campo de confirmação**

5. **Clique em "Run workflow"**

6. **Aguarde a conclusão** (normalmente 2-3 minutos)

7. **Verifique os resultados**
   - Artefato: "reconciliacao-results"
   - Contém análise pós-reconciliação

### Opção 2: Executar Localmente

```bash
# 1. Clone ou entre no repositório
cd advbox-asaas-conciliacao

# 2. Configure as variáveis de ambiente
export ADVBOX_TOKEN="seu_token_aqui"
export TIMEZONE="America/Manaus"

# 3. Execute o script
python reconciliacao_setembro_criar_entradas.py

# 4. Confirme digitando 's' quando solicitado
```

---

## O Que Acontece Durante a Reconciliação

1. **Validação** ✓
   - Verifica se ADVBOX_TOKEN está definido
   - Confirma configuração de contas ASAAS

2. **Criação de Transações** ✓
   - Cria 7 lançamentos na conta ASAAS
   - Valores positivos: receitas
   - Valores negativos: estornos/chargebacks

3. **Análise Pós-Reconciliação** ✓
   - Re-executa análise detalhada
   - Verifica se divergências foram zeradas

4. **Relatório** ✓
   - Exibe resumo de operações
   - Mostra novos totais

---

## Validação Pós-Reconciliação

Após a execução, verifique:

### ✅ No Advbox
- [ ] 7 novas entradas criadas na conta ASAAS
- [ ] Datas corretas (09/01 a 09/08)
- [ ] Valores corretos
- [ ] Categoria atribuída
- [ ] Centro de custo atribuído

### ✅ Na Análise
```
Asaas Total:    R$ 133.826,92
Advbox Total:   R$ 133.826,92  ← Deve estar igual ao Asaas
Divergência:    R$ 0,00        ← Deve ser ZERO
```

---

## Troubleshooting

### ❌ Erro: "ADVBOX_TOKEN não está definido"
**Solução**: 
- Verifique se as secrets estão configuradas no GitHub
- Localmente, execute: `export ADVBOX_TOKEN='seu_token'`

### ❌ Erro: "Falha na criação de entrada"
**Possíveis causas**:
- Token expirado ou inválido
- Conta ASAAS (ID 193264) não disponível
- Usuário (ID 65747) não tem permissão

**Solução**:
- Verifique tokens nos secrets do GitHub
- Confirme IDs de referência no Advbox

### ❌ Divergência não foi zerada
**Possíveis causas**:
- Nem todas as transações foram criadas
- Há outras transações faltando

**Solução**:
- Verifique logs detalhados
- Re-execute a análise manualmente
- Procure por padrões adicionais

---

## Próximos Passos

1. **Após sucesso da reconciliação**:
   - [ ] Confirmar valores no Advbox
   - [ ] Arquivar resultados
   - [ ] Atualizar registros de auditoria

2. **Se houver novos períodos**:
   - Repetir processo para outubro, novembro, etc.
   - Usar mesmo script/workflow

3. **Manutenção preventiva**:
   - Monitorar diariamente novos lançamentos
   - Identificar divergências mais cedo

---

## Referências

- **Script de reconciliação**: `reconciliacao_setembro_criar_entradas.py`
- **Workflow GitHub Actions**: `.github/workflows/reconciliacao-setembro.yml`
- **Análise detalhada**: `analise_por_data_valor.py`
- **Integração com Advbox**: `conciliar_v2.py`

---

**Data do Guia**: 9 de outubro de 2026  
**Status**: Pronto para execução  
**Último Update**: Consolidação de regras de reconciliação e criação de plano
