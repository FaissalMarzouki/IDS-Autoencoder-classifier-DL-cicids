#!/bin/bash

# Script pour démarrer le streaming du dataset avec prédictions

echo "🎯 Streaming du Dataset CICIDS2017 vers Kafka"
echo "=============================================="

# Vérifier les arguments
if [ $# -eq 0 ]; then
    echo "❌ Usage: $0 <chemin_vers_dataset.csv> [options]"
    echo ""
    echo "Options:"
    echo "  --interval SECONDS     Intervalle entre chaque ligne (défaut: 2.0)"
    echo "  --max-rows N          Nombre max de lignes (défaut: tout)"
    echo "  --only-attacks        N'envoyer que les attaques détectées"
    echo ""
    echo "Exemples:"
    echo "  $0 ~/data/cicids2017_cleaned.csv"
    echo "  $0 ~/data/cicids2017_cleaned.csv --interval 1.0 --max-rows 1000"
    echo "  $0 ~/data/cicids2017_cleaned.csv --only-attacks --interval 0.5"
    exit 1
fi

DATASET_PATH=$1
shift

# Vérifier que le fichier existe
if [ ! -f "$DATASET_PATH" ]; then
    echo "❌ Erreur: Fichier non trouvé: $DATASET_PATH"
    exit 1
fi

echo "📊 Dataset: $DATASET_PATH"
echo ""

# Se déplacer dans le dossier dataset_streamer
cd "$(dirname "$0")/../dataset_streamer"

# Activer l'environnement virtuel et utiliser python3.10
if [ -d "/home/ellayli/enset_CCN/s5/IA/project/venv" ]; then
    source /home/ellayli/enset_CCN/s5/IA/project/venv/bin/activate
    PYTHON_CMD="/home/ellayli/enset_CCN/s5/IA/project/venv/bin/python3.10"
else
    PYTHON_CMD="python3"
fi

# Lancer le streaming
$PYTHON_CMD dataset_predictor.py "$DATASET_PATH" "$@"
