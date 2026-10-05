# 🔍 Investigação de Divergências: Próximas Ações

## 📋 Resumo do Status Atual

A análise anterior identificou um **padrão claro de divergências**:
- **8 de 10 dias** têm divergências entre Asaas e Advbox
- **2 de 10 dias** combinam perfeitamente (dias 5 e 7)
- **Padrão identificado**: Transações do tipo `TRANSFER` (PIX) em Asaas não aparecem reconciliadas em Advbox

### Divergências Maiores
1. **Setembro 8**: R$ 78,758.92 em despesas (❌ MAIOR)
2. **Setembro 4**: R$ 11,517.35 em despesas (já analisado)
3. **Setembro 6**: Receita completamente faltando em Advbox (R$ 6,000?)

---

## 🚀 AÇÃO 1: Confirmar Padrão para Setembro 8

### Via GitHub Actions (SEM precisar de tokens locais)

1. **Acesse o repositório no GitHub**
   - URL: `github.com/seu-usuario/advbox-asaas-conciliacao`

2. **Vá para Actions** (aba)
   - Procure por: `"Cache de Dados + Diagnóstico Offline"`

3. **Clique em "Run workflow"**
   - Selecione as opções:
     ```
     atualizar_cache: "sim"
     dia_diagnostico: "2026-09-08"
     ```

4. **Aguarde 3-5 minutos** para conclusão

5. **Analise os resultados**:
   - Veja o output do job (mostrará receitas e despesas de setembro 8)
   - Procure por transações `TRANSFER` no Asaas
   - Verifique se Advbox tem menos itens ou valores diferentes

6. **Download do Cache** (opcional, para análise local):
   - Clique no job concluído
   - Artifact: `transactions-cache`
   - Salve `transactions_cache.json` localmente

### Resultado Esperado

Se a hipótese estiver correta, você verá:

```
💰 ASAAS (Despesas/Taxas)
====================================================================================================

Despesas encontradas: ~40+ itens

1. R$  11,133.35 | TRANSFER
   Descrição: PIX - para ELIZETH SOUZA DA CRUZ DE MELO
   ID: ...

2. R$   3,750.00 | TRANSFER
   Descrição: PIX - para THIAGO
   ID: ...

...

TOTAL ASAAS DESPESAS: R$ 78,758.92

---

💰 ADVBOX (Despesas/Expense)
====================================================================================================

Despesas encontradas: ~15-20 itens (MUITO MENOS que Asaas)

...

TOTAL ADVBOX DESPESAS: R$ ~0.00 (ou muito menor)

---

📊 COMPARAÇÃO
====================================================================================================

DESPESAS:
  Asaas:   R$  78,758.92
  Advbox:  R$      0.00  (ou muito menor)
  Δ:       R$  78,758.92  ✗ Divergência GRANDE
```

---

## 🔧 AÇÃO 2: Análise Profunda (Após ter o cache)

Uma vez que você tiver o `transactions_cache.json`:

### Instalar cache localmente
```bash
# Salve o arquivo baixado do GitHub Actions
cp ~/Downloads/transactions_cache.json ./transactions_cache.json
```

### Analisar qualquer dia
```bash
# Setembro 8 (maior divergência)
DIA_ALVO="2026-09-08" python3 diagnostico_transacoes_offline.py

# Setembro 6 (receita faltando)
DIA_ALVO="2026-09-06" python3 diagnostico_transacoes_offline.py

# Setembro 1 (pequena divergência)
DIA_ALVO="2026-09-01" python3 diagnostico_transacoes_offline.py
```

---

## 📊 AÇÃO 3: Análise de Mapeamento de Tipos

Crie um relatório para entender como os tipos se mapeiam:

```bash
# Ver todos os tipos de transação encontrados
python3 -c "
import json

with open('transactions_cache.json', 'r') as f:
    cache = json.load(f)

# Tipos Asaas
asaas_types = {}
for dia, items in cache['asaas'].items():
    for item in items:
        tipo = item.get('type')
        if tipo:
            asaas_types[tipo] = asaas_types.get(tipo, 0) + 1

print('TIPOS EM ASAAS:')
for tipo, count in sorted(asaas_types.items(), key=lambda x: -x[1]):
    print(f'  {tipo}: {count}x')

print()

# Tipos Advbox
advbox_types = {}
for tx in cache['advbox']:
    tipo = tx.get('entry_type')
    if tipo:
        advbox_types[tipo] = advbox_types.get(tipo, 0) + 1

print('TIPOS EM ADVBOX:')
for tipo, count in sorted(advbox_types.items(), key=lambda x: -x[1]):
    print(f'  {tipo}: {count}x')
"
```

---

## 🎯 Questão Chave para o Usuário

**Antes de continuar a investigação detalhada:**

> **As transações de TRANSFER (PIX) devem ser incluídas na reconciliação entre Asaas e Advbox?**

### Respostas Possíveis:

**Opção A: SIM, devem estar sincronizadas**
- ➜ Problema: Advbox não está recebendo as transações TRANSFER de Asaas
- ➜ Solução: Investigar se é configuração do mapeamento ou problema na API

**Opção B: NÃO, são naturalmente diferentes**
- ➜ Problema: O filtro de reconciliação está incorreto
- ➜ Solução: Excluir TRANSFERs de Asaas ao comparar com Advbox

**Opção C: PARCIAL, apenas alguns TRANSFERs**
- ➜ Problema: Falta de lógica clara sobre quais TRANSFERs incluir
- ➜ Solução: Definir regra de negócio clara

---

## 📝 Checklist para Próxima Sessão

- [ ] Executar workflow "Cache de Dados + Diagnóstico Offline" para setembro 8
- [ ] Confirmar se padrão de TRANSFER se repete
- [ ] Analisar setembro 6 (receita faltando)
- [ ] Mapear tipos de transação em ambos os sistemas
- [ ] Decidir com o usuário: incluir TRANSFERs na reconciliação?
- [ ] Se SIM: criar mapeamento tipo Asaas → Advbox
- [ ] Se NÃO: atualizar scripts de auditoria para excluir TRANSFERs

---

## 🔗 Arquivos Criados/Atualizados

| Arquivo | Propósito |
|---------|-----------|
| `cache_transactions.py` | Salva dados de API em JSON |
| `diagnostico_transacoes_offline.py` | Análise de um dia específico usando cache |
| `.github/workflows/cache-e-diagnostico.yml` | Workflow para gerar cache e diagnosticar |
| `ANALISE_DIVERGENCIAS.md` | Resumo estruturado das divergências encontradas |
| `PROXIMO_PASSO.md` | Este arquivo - instruções para continuar |

---

## 💡 Dica Rápida

Se você quer ver os dados imediatamente sem usar GitHub Actions:
```bash
# Editar conciliar_v2.py para usar tokens mock/exemplo
# OU
# Usar curl direto na API (mas precisa dos tokens corretos):

curl -H "Authorization: Bearer $ADVBOX_TOKEN" \
  https://api.advbox.com.br/v1/transactions \
  | jq . | head -50
```

---

**Status**: Pronto para continuar investigação
**Tempo estimado**: 5-10 min para confirmar padrão via GitHub Actions
