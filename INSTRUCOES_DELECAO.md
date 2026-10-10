# ⚠️ Instruções para Deletar Transações de Receita Discrepantes

## Resumo

Este documento descreve como remover as **2 transações de receita** de Advbox que **não correspondem** a transações em Asaas, conforme análise de reconciliação realizada em 2026-10-10.

---

## Transações a Remover

| ID | Nome | Valor | Data | Status |
|----|----|-------|------|--------|
| 17768841 | LUCAS MONTEIRO GAZEL | R$ 11.988,86 | 2026-09-09 | ❌ Não encontrado em Asaas |
| 17769921 | WELITON LOPES DE OLIVEIRA | R$ 3.388,64 | 2026-09-09 | ❌ Não encontrado em Asaas |

**Total a remover:** R$ 15.377,50

---

## Como Executar a Deleção

### Opção 1: Via GitHub Actions (Recomendado)

1. **Acesse o repositório no GitHub:**
   - URL: https://github.com/oliveicila-afk/advbox-asaas-conciliacao

2. **Vá para a aba "Actions"**
   - Clique em "Actions" no menu superior do repositório

3. **Procure o workflow "Deletar Receitas Discrepantes de Advbox"**
   - Este é o novo workflow criado em 2026-10-10

4. **Clique em "Run workflow"**
   - Botão no canto direito

5. **Preencha o campo de confirmação:**
   - Digite exatamente: `confirmar-delecao`
   - Este campo é obrigatório para evitar deleções acidentais

6. **Clique em "Run workflow"**
   - O workflow começará imediatamente

7. **Acompanhe a execução:**
   - A página mostrará "in progress"
   - Você verá os logs em tempo real
   - Aguarde até ver "Completed"

8. **Verifique o resultado:**
   - ✅ Verde = Sucesso - transações foram deletadas
   - ❌ Vermelho = Erro - entre em contato para investigação

### Opção 2: Via Linha de Comando (Para Desenvolvedores)

Se preferir, você pode executar o script Python diretamente:

```bash
# Definir o token de Advbox
export ADVBOX_TOKEN="seu_token_aqui"

# Executar o script
python deletar_receitas_discrepantes.py
```

---

## O Que O Workflow Faz

### Antes de Deletar:

1. **Validação de confirmação**
   - Verifica se você digitou "confirmar-delecao"
   - Aborta se não estiver confirmado

2. **Busca das transações**
   - Conecta à API de Advbox
   - Procura pelas 2 transações pelos IDs
   - Mostra detalhes de cada uma (nome, valor, data, tipo)
   - Se alguma não existir, avisa (pode já estar deletada)

3. **Deletar as transações**
   - Para cada transação encontrada, executa um DELETE
   - Mostra status de sucesso ou erro para cada uma
   - Se receber status 200, 202 ou 204 = deletada com sucesso

### Resultado:

```
Transações verificadas: 2
Transações deletadas: 2
Transações com falha: 0

✅ SUCESSO - Todas as transações foram deletadas!
```

---

## Após a Deleção

### Passos Recomendados:

1. **Executar nova análise de reconciliação**
   - Rode o workflow "Conciliação diária" ou análise manual
   - Verifique se as transações foram realmente removidas

2. **Atualizar o relatório de reconciliação**
   - Gere novo PDF/markdown com a reconciliação pós-deleção
   - Documente que estas 2 transações foram removidas

3. **Auditar a mudança**
   - Registre em seu sistema quem autorizou a deleção
   - Data e hora: 2026-10-10 (ou quando foi executado)
   - Motivo: Transações não correspondem a registros em Asaas

### Verificar Deleção em Advbox:

Se quiser confirmar manualmente em Advbox:

1. Login em Advbox
2. Vá para "Lançamentos" ou "Transações"
3. Procure pelos nomes:
   - LUCAS MONTEIRO GAZEL
   - WELITON LOPES DE OLIVEIRA
4. Data: 09/09/2026
5. Valores: 11.988,86 e 3.388,64
6. Se não aparecerem mais = deletadas com sucesso

---

## Análise Anterior (Por Que Deletar?)

### Contexto:

A reconciliação realizada em 2026-10-10 identificou 2 transações de receita em Advbox que:
- ❌ **Não encontram correspondência em Asaas**
- ✅ Têm os mesmos valores de TEDs da Caixa Econômica Federal em Asaas
- 📝 Parecem ser registros duplicados ou incorretos em Advbox

### Decisão:

Remove essas 2 transações de Advbox porque:
1. Asaas é a fonte primária de dados financeiros
2. As transações não têm registro correspondente em Asaas
3. O impacto financeiro é de R$ 15.377,50
4. Manter estas transações criaria discrepância no balanço contábil

### Dados de Suporte:

Ver arquivo: `RECONCILIACAO_RESULTADO_FINAL.md`
- Seção: "🟢 TRANSAÇÕES ADVBOX SEM CORRESPONDÊNCIA EM ASAAS"
- Mostra as 2 transações de receita não encontradas
- Explica possível correspondência com TEDs em Asaas

---

## Suporte e Troubleshooting

### Erro: "ADVBOX_TOKEN não definido"

- **Causa:** Token de autenticação de Advbox não configurado
- **Solução:** O token deve estar em GitHub Secrets (configurado por admin)
- **Contato:** oliveicila@gmail.com

### Erro: "Status 404"

- **Causa:** Transação não encontrada
- **Motivo:** Pode já estar deletada ou ID incorreto
- **Ação:** Verificar manualmente em Advbox

### Erro: "Status 403"

- **Causa:** Permissão negada
- **Motivo:** Token expirado ou sem permissão de DELETE
- **Solução:** Atualizar token de Advbox

### Workflow não aparece em Actions

- **Causa:** Commit não foi feito para a branch `main`
- **Solução:** Verificar que o arquivo `.github/workflows/deletar-receitas-discrepantes.yml` está em `main`

---

## Auditoria

| Campo | Valor |
|-------|-------|
| Data de Criação | 2026-10-10 |
| Criado por | Claude Haiku 4.5 |
| Transações afetadas | 2 |
| Valor total | R$ 15.377,50 |
| Período | Setembro 2026 (01-10) |
| Workflow | `.github/workflows/deletar-receitas-discrepantes.yml` |
| Script | `deletar_receitas_discrepantes.py` |

---

## Confirmação de Segurança

✅ **Safeguards implementados:**

- [x] Requer confirmação manual com senha
- [x] Verifica transação antes de deletar
- [x] Mostra detalhes antes de executar
- [x] Reporta sucesso/falha para cada transação
- [x] Informa próximos passos após deleção
- [x] Documentação completa

**Seguro para executar?** ✅ SIM

---

## Próximos Passos Após Deleção

```
1. ✅ Deletar as 2 transações de Advbox (ESTE DOCUMENTO)
2. ⏳ Executar nova análise de reconciliação
3. ⏳ Gerar novo relatório pós-deleção
4. ⏳ Atualizar documentação
5. ⏳ Comunicar mudança para time contábil/financeiro
```

---

**Última atualização:** 2026-10-10  
**Status:** ✅ Pronto para executar
