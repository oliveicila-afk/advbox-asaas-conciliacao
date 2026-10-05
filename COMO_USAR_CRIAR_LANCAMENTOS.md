# Como Usar: Criar Lançamentos Faltantes

## Resumo

O script `criar_lancamentos.py` cria automaticamente as **8 receitas faltantes** no Advbox que existem no Asaas, e delete as **4 entradas fantasmas** (erros de conciliação anterior).

**Data de reconciliação:** 2026-09-09

## O Que o Script Faz

### Criação (8 itens):
1. TED recebida - fatura nr. 906142104 Caixa Econômica Federal - R$ 11.988,86
2. TED recebida - fatura nr. 905869074 Caixa Econômica Federal - R$ 3.388,64
3. Antecipação - fatura nr. 904531587 CARLOS ALBERTO DOS SANTOS FERREIRA - R$ 100,50
4. Antecipação - fatura nr. 904531355 ELISABETH BRITTO DA COSTA - R$ 374,25
5. Antecipação - fatura nr. 904531266 MARINETE GERALDA DA SILVA - R$ 100,50
6. Cobrança recebida - fatura nr. 878636158 CARLOS ALBERTO DOS SANTOS FERREIRA - R$ 100,50
7. Cobrança recebida - fatura nr. 878442693 ELISABETH BRITTO DA COSTA - R$ 374,25
8. Cobrança recebida - fatura nr. 878442589 MARINETE GERALDA DA SILVA - R$ 100,50

**Total de receitas:** R$ 16.527,50

### Deleção (4 itens):
1. TAXA DE COMUNICAÇÃO - CONSOLIDADO DO DIA (ID: 17592666)
2. TAXA DE ANTECIPAÇÃO - CONSOLIDADO DO DIA (ID: 17592668)
3. PROCESSO NO 0046677-39.2025.8.04.1000 - HONORARIOS SUCUMBENCIAIS (ID: 17768841)
4. PROCESSO NO 0113832-93.2024.8.04.1000 - TED RECEBIDA (ID: 17769921)

## Pré-requisitos

✓ Python 3.11+ instalado
✓ `requests` library instalado (ver requirements.txt)
✓ Arquivo `analise_2026-09-09.json` presente no diretório
✓ **ADVBOX_TOKEN válido do GitHub Secrets**

## Como Executar

### Opção 1: Com Token Local (Teste)

Se você tiver o token Advbox:

```bash
cd /home/claude/oliveicila-afk/advbox-asaas-conciliacao

# Defina a variável de ambiente
export ADVBOX_TOKEN="seu_token_aqui"

# Execute o script
python3 criar_lancamentos.py
```

### Opção 2: Via GitHub Actions (Recomendado)

Se você estiver em um ambiente GitHub Actions com secrets configurados:

```yaml
- name: Criar lançamentos faltantes
  env:
    ADVBOX_TOKEN: ${{ secrets.ADVBOX_TOKEN }}
  run: python criar_lancamentos.py
```

### Opção 3: Command Line Direta

```bash
ADVBOX_TOKEN="seu_token_aqui" python3 criar_lancamentos.py
```

## Saída Esperada

```
[HH:MM:SS] ============================================================
[HH:MM:SS] CRIAÇÃO DE LANÇAMENTOS FALTANTES - 2026-09-09
[HH:MM:SS] ============================================================
[HH:MM:SS]
[HH:MM:SS] 📝 PASSO 1: Criando receitas faltando (8 itens)
[HH:MM:SS] ============================================================
[HH:MM:SS] Criando: TED recebida - fatura nr. 906142104 Caixa Economica Federal - R$ 11988.86
[HH:MM:SS]   ✓ Criado com sucesso
[HH:MM:SS] Criando: TED recebida - fatura nr. 905869074 Caixa Economica Federal - R$ 3388.64
[HH:MM:SS]   ✓ Criado com sucesso
...
[HH:MM:SS] ✓ 8/8 receitas criadas com sucesso
[HH:MM:SS]
[HH:MM:SS] 🗑️  PASSO 2: Deletando entradas fantasmas (4 itens)
[HH:MM:SS] ============================================================
[HH:MM:SS] Deletando: TAXA DE COMUNICAÇÃO - CONSOLIDADO DO DIA... (ID: 17592666)
[HH:MM:SS]   ✓ Deletado com sucesso
...
[HH:MM:SS] ✓ 4/4 entradas fantasmas deletadas
[HH:MM:SS]
[HH:MM:SS] ============================================================
[HH:MM:SS] RESUMO DA OPERAÇÃO
[HH:MM:SS] ============================================================
[HH:MM:SS] Receitas criadas: 8/8
[HH:MM:SS] Fantasmas deletados: 4/4
[HH:MM:SS]
[HH:MM:SS] ✅ SUCESSO! Reconciliação completada para 2026-09-09
```

## Tratamento de Erros

### Erro: ADVBOX_TOKEN não está definido

```
❌ ERRO: ADVBOX_TOKEN não está definido
Use: ADVBOX_TOKEN='seu_token' python criar_lancamentos.py
```

**Solução:** Defina a variável de ambiente com seu token:
```bash
export ADVBOX_TOKEN="seu_token_aqui"
```

### Erro 401 (Não Autorizado)

```
[HH:MM:SS] Criando: ... - R$ XXX.XX
[HH:MM:SS]   ❌ Erro 401: {...}
```

**Causas possíveis:**
- Token expirado ou revogado
- Token inválido ou mal formatado
- Permissões insuficientes no Advbox

**Solução:** 
- Gere um novo token no dashboard do Advbox
- Atualize o GitHub Secret: `Settings → Secrets and variables → Actions → ADVBOX_TOKEN`

### Erro 404 (Não Encontrado)

Pode indicar que a API mudou ou o endpoint está incorreto.

**Solução:** Verificar se a versão da API Advbox é a esperada.

## Segurança

⚠️ **NUNCA exponha seu ADVBOX_TOKEN**

- Use variáveis de ambiente
- Use GitHub Secrets para CI/CD
- Não inclua o token em commits de git
- Se exposto, regenere imediatamente no dashboard

## Logs e Debugging

O script usa timestamps para cada operação. Para ver mais detalhes:

```bash
# Redirecionar para arquivo
ADVBOX_TOKEN="..." python3 criar_lancamentos.py | tee lancamentos.log

# Depois verificar o log
cat lancamentos.log
```

## Próximos Passos (após sucesso)

1. ✅ Verificar no Advbox se as receitas foram criadas
2. ✅ Verificar se as 4 entradas fantasmas foram deletadas
3. ✅ Conferir saldo total: deve ser R$ 18.150,45 em receitas
4. ✅ Fazer push do código atualizado para Git

```bash
git add criar_lancamentos.py COMO_USAR_CRIAR_LANCAMENTOS.md
git commit -m "Adicionar script para criar lançamentos faltantes (2026-09-09)"
git push origin main
```

## Referências

- Script: `criar_lancamentos.py`
- Análise: `analise_2026-09-09.json`
- Documentação Advbox: `DIAGNOSTICO_ERRO_401.md`, `ANALISE_TECNICA.md`

---

**Data de criação:** 2026-10-05  
**Responsável:** Claude Haiku 4.5  
**Status:** Pronto para usar
