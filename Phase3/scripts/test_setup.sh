#!/bin/bash

# Script de test rapide Phase 3
# Ce script teste que tous les composants sont prêts

echo "🔍 TEST DE CONFIGURATION PHASE 3"
echo "=================================="
echo ""

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$(dirname "$0")/.."

# 1. Test de la configuration Python
echo "1️⃣ Test config.py..."
if python config.py > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Configuration Python valide${NC}"
else
    echo -e "${RED}❌ Erreur dans config.py${NC}"
    python config.py
    exit 1
fi

# 2. Vérifier que Kafka est démarré
echo ""
echo "2️⃣ Vérification Kafka..."
if docker ps | grep -q kafka; then
    echo -e "${GREEN}✅ Kafka est démarré${NC}"
    
    # Tester la connexion
    if docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Kafka est accessible${NC}"
    else
        echo -e "${RED}❌ Kafka ne répond pas${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Kafka n'est pas démarré${NC}"
    echo "Démarrage de Kafka..."
    cd ../kafka_docker_config
    docker-compose up -d
    echo "Attente 30 secondes..."
    sleep 30
    cd ../Phase3
    
    if docker ps | grep -q kafka; then
        echo -e "${GREEN}✅ Kafka démarré${NC}"
    else
        echo -e "${RED}❌ Impossible de démarrer Kafka${NC}"
        exit 1
    fi
fi

# 3. Vérifier les topics
echo ""
echo "3️⃣ Vérification des topics Kafka..."

# Créer ids-alerts si nécessaire
if ! docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | grep -q "ids-alerts"; then
    echo "Création du topic ids-alerts..."
    docker exec kafka kafka-topics --create --if-not-exists \
        --topic ids-alerts \
        --bootstrap-server localhost:9092 \
        --partitions 1 \
        --replication-factor 1 > /dev/null 2>&1
    echo -e "${GREEN}✅ Topic ids-alerts créé${NC}"
else
    echo -e "${GREEN}✅ Topic ids-alerts existe${NC}"
fi

# Créer ids-explanations si nécessaire
if ! docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | grep -q "ids-explanations"; then
    echo "Création du topic ids-explanations..."
    docker exec kafka kafka-topics --create --if-not-exists \
        --topic ids-explanations \
        --bootstrap-server localhost:9092 \
        --partitions 1 \
        --replication-factor 1 > /dev/null 2>&1
    echo -e "${GREEN}✅ Topic ids-explanations créé${NC}"
else
    echo -e "${GREEN}✅ Topic ids-explanations existe${NC}"
fi

# 4. Vérifier le fichier .env
echo ""
echo "4️⃣ Vérification .env..."
if [ -f ".env" ]; then
    if grep -q "GROQ_API_KEY=gsk_" .env; then
        echo -e "${GREEN}✅ GROQ_API_KEY configurée${NC}"
    else
        echo -e "${YELLOW}⚠️  GROQ_API_KEY non configurée ou invalide${NC}"
    fi
    
    # Vérifier le port Kafka
    if grep -q "KAFKA_BOOTSTRAP_SERVERS=localhost:9092" .env; then
        echo -e "${GREEN}✅ Port Kafka correct (9092)${NC}"
    else
        echo -e "${YELLOW}⚠️  Port Kafka dans .env : $(grep KAFKA_BOOTSTRAP_SERVERS .env)${NC}"
    fi
else
    echo -e "${RED}❌ Fichier .env non trouvé${NC}"
    exit 1
fi

# 5. Vérifier les dépendances Python
echo ""
echo "5️⃣ Vérification des dépendances Python..."

missing_deps=()

if ! python -c "import kafka" 2>/dev/null; then
    missing_deps+=("kafka-python")
fi

if ! python -c "import streamlit" 2>/dev/null; then
    missing_deps+=("streamlit")
fi

if ! python -c "import groq" 2>/dev/null; then
    missing_deps+=("groq")
fi

if ! python -c "import torch" 2>/dev/null; then
    missing_deps+=("torch")
fi

if [ ${#missing_deps[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ Toutes les dépendances sont installées${NC}"
else
    echo -e "${YELLOW}⚠️  Dépendances manquantes: ${missing_deps[*]}${NC}"
    echo "Installation..."
    pip install -q kafka-python streamlit groq torch pandas numpy scikit-learn joblib python-dotenv plotly
    echo -e "${GREEN}✅ Dépendances installées${NC}"
fi

# 6. Vérifier le dataset
echo ""
echo "6️⃣ Vérification du dataset CICIDS2017..."
DATASET_DIR="/home/ellayli/enset_CCN/s5/IA/project/IDS-Autoencoder-classifier-DL-cicids/MachineLearningCSV/MachineLearningCVE"

if [ -d "$DATASET_DIR" ]; then
    file_count=$(ls -1 "$DATASET_DIR"/*.csv 2>/dev/null | wc -l)
    if [ $file_count -gt 0 ]; then
        echo -e "${GREEN}✅ Dataset trouvé : $file_count fichiers CSV${NC}"
        ls -lh "$DATASET_DIR"/*.csv | head -3
    else
        echo -e "${RED}❌ Aucun fichier CSV trouvé dans $DATASET_DIR${NC}"
    fi
else
    echo -e "${RED}❌ Dossier dataset non trouvé : $DATASET_DIR${NC}"
fi

# Résumé
echo ""
echo "=================================="
echo -e "${GREEN}🎉 TESTS TERMINÉS${NC}"
echo ""
echo "📋 Prochaines étapes :"
echo "  1. Démarrer le service LLM : python -m llm_service.main"
echo "  2. Démarrer le dashboard : streamlit run dashboard/app.py"
echo "  3. Streamer le dataset : python dataset_streamer/dataset_predictor.py <csv_file>"
echo ""
echo "📖 Guide complet : INTEGRATION_GUIDE.md"
echo "=================================="
