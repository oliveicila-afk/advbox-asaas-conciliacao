# Conciliação Diária Advbox × Asaas

Sistema automatizado para conciliar receitas de honorário entre a plataforma Advbox (gestão jurídica) e Asaas (gateway de pagamentos). Identifica receitas faltando, classifica por tipo (êxito/sucumbencial), resolve centros de custo e posta lançamentos automaticamente quando possível.

## 🎯 O Que Faz

1. **Busca receitas do dia** na Asaas (financialTransactions)
2. **Compara com lançamentos** no Advbox (transactions)
3. **Identifica receitas faltando** por matching de nome + valor
4. **Classifica honorários** como êxito ou sucumbencial (lendo protocolo do processo)
5. **Resolve categorias e centros de custo** por:
   - Precedente (se houver lançamento anterior do mesmo processo)
   - Análise de tarefas/descrições
   - Protocolos (êxito/sucumbencial detectado no histórico)
   - **NOVO (out/2026)**: Tese + Origem do cliente
6. **Posta automaticamente** (receita + despesa de repasse quando aplicável)
7. **Gera relatório PDF** mascarando dados sensíveis

## 📋 Requisitos

- Python 3.11+
- Tokens de autenticação:
  - `ADVBOX_TOKEN` (API token)
  - `ASAAS_TOKEN` (API token)
- (Opcional) Credenciais de email para enviar relatório:
  - `SMTP_USER` (Gmail ou outro SMTP)
  - `SMTP_PASS` (senha de app)
  - `EMAIL_DESTINO`

## 🚀 Como Usar

### Instalação

```bash
pip install -r requirements.txt
```

### Execução Local

```bash
# Usar data de ontem (padrão):
python3 conciliar_v2.py

# Especificar data:
TARGET_DATE=2026-09-28 python3 conciliar_v2.py

# Simular sem gravar (DRY_RUN):
TARGET_DATE=2026-09-28 DRY_RUN=true python3 conciliar_v2.py

# Variáveis de ambiente:
export ADVBOX_TOKEN="seu_token"
export ASAAS_TOKEN="seu_token"
export SMTP_USER="seu_email@gmail.com"
export SMTP_PASS="sua_senha_app"
export EMAIL_DESTINO="destino@example.com"
export TIMEZONE="America/Manaus"
```

### Via GitHub Actions (Automatizado)

A conciliação roda automaticamente todo dia às 05:00 UTC (01:00 em Manaus). Você também pode:

1. Ir para **Actions** → **Conciliação diária Advbox x Asaas**
2. Clicar em **Run workflow**
3. Preencher:
   - **Target Date:** 2026-09-28 (ou deixar em branco para ontem)
   - **DRY_RUN:** true (primeiro!) ou false
4. O PDF fica disponível em **Artifacts** por 30 dias

Para a retroconciliação por intervalo:

1. Abra **Actions** → **Criar Lançamentos Faltantes** → **Run workflow**.
2. Informe as datas inicial e final.
3. Mantenha **dry_run** ativado na primeira execução para revisar o plano.
4. Só desative **dry_run** depois de conferir a simulação; a execução real cria/corrige e cancela lançamentos no AdvBox.

Esse workflow busca os dados novamente para cada intervalo e não usa os arquivos `analise_*.json`
versionados no repositório. O matching considera data, direção e valor em centavos, preserva
duplicidades e deixa a execução bloqueada quando há tipos sem regra, categorias inexistentes ou
excesso em categoria consolidada. Receitas só são criadas quando as regras existentes identificam
processo, categoria e centro de custo; não há categoria padrão de fallback. Taxas bancárias por
cliente sem correspondência inequívoca continuam manuais, conforme a regra já existente.

Se o workflow registrar `401 Unauthenticated`, confira/atualize os secrets `ADVBOX_TOKEN` e
`ASAAS_TOKEN` em **Settings** → **Secrets and variables** → **Actions**. A simulação e a análise
não corrigem credenciais inválidas.

## 📊 Fluxo de Classificação

```
Receita Asaas não encontrada no Advbox
        ↓
Identifica processo via externalReference
        ↓
CAMADA 1: Procura precedente (mesma processo, receita anterior)
        ↓
CAMADA 2: Analisa tarefas/descrições do processo (se não achou)
        ↓
CAMADA 3: Verifica juros/multas (validação)
        ↓
CAMADA 4: Sugere centro de custo por origin do cliente
        ↓
CAMADA 4B: [NOVO] Resolve tese + origem → centro de custo
        ↓
CAMADA 5: Lê protocolo (histórico) → êxito/sucumbencial + valor repasse
        ↓
✓ Tem categoria + centro de custo + protocolo válido?
   → POST: Receita (valor cheio) + Despesa (repasse cliente)
   → PDF: Listado como "Corrigido automaticamente"

✗ Falta algo?
   → Fica manual: PDF mostra "Receita faltando - precisa decisão manual"
```

## 🏗️ Arquitetura

### Funções Principais

#### Leitura de Dados
- `advbox_get_all_transactions()` - busca lançamentos do Advbox
- `asaas_get_financial_transactions_do_dia(data)` - busca receitas da Asaas
- `advbox_get_all_lawsuits()` - busca todos os processos

#### Identificação de Processo
- `identificar_processo_por_referencia(ref, lawsuits)` - acha processo pelo número
- `advbox_get_customer(id)` - busca dados do cliente (origin)
- `advbox_get_protocolo_textos(lawsuit_id)` - lê histórico/protocolo

#### Classificação
- `interpretar_protocolo(textos)` - extrai êxito/sucumbencial/repasse do protocolo (v2.0: regex expandidos)
- `classificar_honorario(protocolo)` - decide êxito vs sucumbencial
- `categoria_por_tese(tipo, tese)` - monta nome da categoria
- `categoria_repasse_cliente(tese)` - categoria de despesa

#### Resolução de Centros de Custo (v2.0 +)
- `_mapa_tese_grupo()` - mapeia tese → grupo
- `resolver_centro_custo_por_tese_e_origem(tese, origem)` - combina tese + origem
- `resolver_centro_custo_id(nome)` - converte nome → ID numérico

#### Posting
- `advbox_post(payload)` - cria lançamento (receita/despesa)
- `advbox_put(id, payload)` - atualiza lançamento

#### Geração de Relatório
- `calcular_fluxo_caixa_do_dia(items, data)` - entradas + saídas
- `gerar_pdf(...)` - relatório com mascaramento
- `enviar_email(...)` - entrega do PDF

### Estrutura de Dados

#### Receita Enriquecida (`_processo_identificado`)
```python
{
    "processo": "0000929-79.2026.8.04.2800",
    "cliente": "Nome Fictício",
    "lawsuits_id": 5836169,
    "categoria_final": "HONORÁRIOS CONTRATUAIS DE ÊXITO-RMC",
    "centro_custo_sugerido": "RMC-ESCRITÓRIO / DIRETA",
    "confianca_categoria": "precedente|protocolo/exito|media|baixa",
    "origem_cliente": "ESCRITÓRIO",
    "tese": "RMC",
    "tipo_honorario": "exito|sucumbencial|None",
    "protocolo": {
        "tem_protocolo": True,
        "exito": 1234.56,
        "sucumbencial": None,
        "repasse_cliente": 234.56,
        "valor_creditado": None,
    }
}
```

## 🔒 Segurança

- **Mascaramento:** Nomes de cliente (Cliente #XXXX), CPFs (***-***-***-XX) no PDF
- **Sem logs sensíveis:** Tokens, CPFs, dados bancários nunca printados
- **Travas de automação:**
  1. Precisa categoria_id E centro_custo_id
  2. Se protocolo informa valor creditado ≠ valor recebido → manual
  3. DRY_RUN simula tudo sem gravar nada
- **Rastreabilidade:** IDs de transação sempre visíveis

## 📁 Arquivos

- `conciliar_v2.py` - **script principal** (lógica de conciliação + posting)
- `diagnostico_advbox.py` - script de diagnóstico (lê settings/posts sem modificar)
- `requirements.txt` - dependências (requests, fpdf2, zoneinfo, etc.)
- `.github/workflows/conciliacao-diaria.yml` - agendamento automático
- Documentação:
  - `ARQUITETURA_v2.md` - design técnico
  - `IMPLEMENTACAO_v2_GUIA.md` - como foi implementado
  - `CHANGELOG_v2.md` - histórico de v1 → v2
  - `CHANGELOG_TESE_ORIGEM.md` - detalhes da melhoria de out/2026
  - `RESUMO_MELHORIAS_OCT_2026.md` - resumo + instruções de teste
- Testes:
  - `test_tese_origem_mapping.py` - 10 testes de mapeamento tese+origem
  - `test_protocolo_regex.py` - 5 testes de parsing de protocolo

## 🧪 Testes

```bash
# Teste de mapeamento (sem API)
python3 test_tese_origem_mapping.py
# Esperado: 10/10 testes passam ✓

# Teste de regex de protocolo (sem API)
python3 test_protocolo_regex.py
# Esperado: 5/5 testes passam ✓

# Teste em DRY_RUN (com API, sem gravar)
TARGET_DATE=2026-09-28 DRY_RUN=true python3 conciliar_v2.py
```

## 📝 Exemplos de Casos Resolvidos

### Caso 1: Receita com Precedente
- **Receita:** R$ 9.351,31 (processo 5836169)
- **Histórico:** Lançamento anterior no Advbox → categoria + centro de custo copiados
- **Resultado:** ✓ Postada automaticamente

### Caso 2: Receita com Tese + Origem (NOVO out/2026)
- **Receita:** R$ 1.588,73 (origem=ESCRITÓRIO, tese=RMC)
- **Antes:** Falhava porque centro de custo era None
- **Agora:** CAMADA 4B resolve RMC + ESCRITÓRIO → "RMC-ESCRITÓRIO / DIRETA"
- **Resultado:** ✓ Postada automaticamente

### Caso 3: Receita com Protocolo Compacto (NOVO out/2026)
- **Receita:** R$ 3.608,27 (protocolo com formato "Êxito: R$ X. Repasse: R$ Y.")
- **Antes:** Regex original não capturava este formato
- **Agora:** V2.0 regex com padrões expandidos consegue capturar
- **Resultado:** ✓ Parseado + Postada automaticamente

### Caso 4: Receita Ambígua → Manual
- **Receita:** R$ 5.000,00 (sem processo identificável ou protocolo incompleto)
- **Motivo para ficar manual:**
  - Não consegue bater número do processo
  - OU não consegue resolver categoria
  - OU não consegue resolver centro de custo
- **Resultado:** ✗ Listada no PDF para decisão manual

## 🔧 Troubleshooting

### "ERRO: categoria_id and/ou centro_custo_id não configurados"
- Log dirá se faltou categoria_id ou centro_custo_id
- Verificar /settings do Advbox pra garantir que a categoria/centro existe
- Adicionar novo padrão regex se protocolo tem formato desconhecido

### "Receita faltando: precisa decisão manual"
- Checar log diagnóstico (linha `[DIAG receita R$ XXX]`)
- Rodar `diagnostico_advbox.py` pra explorar processo no Advbox
- Se tese está faltando no mapping: adicionar novo tipo de ação em /settings
- Se origem não está em nenhum centro de custo: avaliar se é typo

### "PDF com divergências após correção"
- Corrigiu automático mas ainda faltam receitas?
- Possivelmente há outros padrões de protocolo ou categorias não mapeadas
- Rodar em DRY_RUN=true pra ver o que seria postado antes de gravar

## 📞 Suporte

Para dúvidas sobre:
- **Lógica de classificação:** ver `ARQUITETURA_v2.md`
- **Implementação:** ver `IMPLEMENTACAO_v2_GUIA.md`
- **Tese + Origem:** ver `CHANGELOG_TESE_ORIGEM.md`
- **Como testar:** ver `RESUMO_MELHORIAS_OCT_2026.md`

---

**Última atualização:** 2026-10-04  
**Versão:** 2.0 + melhorias de outubro 2026  
**Status:** ✓ Pronto para produção
