#!/bin/bash
# Wrapper script para facilitar a execução do script de lançamentos

set -e

echo "=========================================="
echo "Executar Script de Lançamentos"
echo "Reconciliação: 2026-09-09"
echo "=========================================="
echo ""

# Check if token is provided
if [ -z "$ADVBOX_TOKEN" ]; then
    echo "❌ ERRO: ADVBOX_TOKEN não está definido"
    echo ""
    echo "Como usar:"
    echo "  Opção 1 (GitHub CLI - recomendado):"
    echo "    gh secret list -L 1000 | grep ADVBOX_TOKEN | awk '{print \"export ADVBOX_TOKEN=\" \$1}'"
    echo ""
    echo "  Opção 2 (Token manual):"
    echo "    export ADVBOX_TOKEN='seu_token'"
    echo ""
    echo "Depois execute:"
    echo "    bash executar.sh"
    echo ""
    exit 1
fi

# Verify token format
if [[ ! "$ADVBOX_TOKEN" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "⚠️  Aviso: Token parece inválido (caracteres inesperados)"
    echo "Token: ${ADVBOX_TOKEN:0:10}...${ADVBOX_TOKEN: -10}"
    read -p "Deseja continuar? (s/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        exit 1
    fi
fi

echo "📋 Token configurado"
echo "   ${ADVBOX_TOKEN:0:20}...${ADVBOX_TOKEN: -10}"
echo ""

# Check if script exists
if [ ! -f "criar_lancamentos.py" ]; then
    echo "❌ ERRO: criar_lancamentos.py não encontrado"
    echo "Execute este script no diretório raiz do projeto"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ ERRO: Python 3 não encontrado"
    exit 1
fi

# Check requests library
if ! python3 -c "import requests" 2>/dev/null; then
    echo "❌ ERRO: requests library não está instalada"
    echo "Execute: pip install requests"
    exit 1
fi

echo "✓ Python 3 OK"
echo "✓ requests library OK"
echo ""
echo "=========================================="
echo "Executando script..."
echo "=========================================="
echo ""

# Run the script
python3 criar_lancamentos.py

exit_code=$?

echo ""
echo "=========================================="
if [ $exit_code -eq 0 ]; then
    echo "✅ Script executado com sucesso!"
    echo ""
    echo "Próximos passos:"
    echo "  1. Verificar no Advbox se as receitas foram criadas"
    echo "  2. Conferir se as entradas fantasmas foram deletadas"
    echo "  3. Fazer novo teste de reconciliação"
else
    echo "❌ Script falhou com código de erro: $exit_code"
    echo ""
    echo "Verifique:"
    echo "  - Token está correto?"
    echo "  - Tem permissão para criar/deletar no Advbox?"
    echo "  - Está na rede correta?"
fi
echo "=========================================="

exit $exit_code
