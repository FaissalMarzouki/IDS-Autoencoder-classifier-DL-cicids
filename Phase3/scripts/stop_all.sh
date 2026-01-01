#!/bin/bash

# Script pour arrêter tous les services

echo "⏹️  Arrêt du système IDS Phase 3..."

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Arrêter le service LLM
if [ -f ".llm_service.pid" ]; then
    LLM_PID=$(cat .llm_service.pid)
    if ps -p $LLM_PID > /dev/null; then
        echo "Arrêt du service LLM (PID: $LLM_PID)..."
        kill $LLM_PID
        rm .llm_service.pid
        echo -e "${GREEN}✅ Service LLM arrêté${NC}"
    else
        echo "Service LLM déjà arrêté"
        rm .llm_service.pid
    fi
fi

# Arrêter Kafka
echo "Arrêt de Kafka..."
cd ../kafka_docker_config
docker-compose down
echo -e "${GREEN}✅ Kafka arrêté${NC}"

echo ""
echo -e "${GREEN}✅ Tous les services sont arrêtés${NC}"
