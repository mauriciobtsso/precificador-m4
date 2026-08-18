#!/usr/bin/env bash
# Script de Build Robusto para Render - M4 Tática
# Previne falhas 502/Timeout do PyPI com retentativas

set -o errexit

echo "🚀 Iniciando build robusto..."

# 1. Atualizar o pip para a versão mais estável
python -m pip install --upgrade pip

# 2. Instalação com retentativas (máximo 3 vezes)
# O erro 502 é temporário no PyPI, isso resolve 99% dos casos
MAX_RETRIES=3
RETRY_COUNT=0

until [ $RETRY_COUNT -ge $MAX_RETRIES ]
do
   echo "📦 Instalando dependências (Tentativa $((RETRY_COUNT+1))/$MAX_RETRIES)..."
   pip install -r requirements.txt && break
   RETRY_COUNT=$((RETRY_COUNT+1))
   echo "⚠️ Falha na rede. Aguardando 5 segundos para tentar novamente..."
   sleep 5
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Erro crítico: Falha persistente na conexão com PyPI após $MAX_RETRIES tentativas."
    exit 1
fi

# 3. Rodar migrations automaticamente (Opcional, mas recomendado)
echo "🔧 Rodando migrations do banco de dados..."
flask db upgrade

echo "✅ Build concluído com sucesso!"
