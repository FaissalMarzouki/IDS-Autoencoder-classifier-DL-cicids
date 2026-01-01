"""
Producer Kafka pour les explications LLM
"""
from kafka import KafkaProducer
import json
import logging
from typing import Dict, Any
import sys
import os

# Ajouter le répertoire parent au path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import KAFKA_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExplanationProducer:
    """Producer Kafka pour publier les explications LLM"""
    
    def __init__(self):
        self.topic = KAFKA_CONFIG['topics']['explanations']
        self.bootstrap_servers = KAFKA_CONFIG['bootstrap_servers']
        self.producer = None
        
    def start(self) -> None:
        """Initialise le producer Kafka"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                **KAFKA_CONFIG['producer_config']
            )
            logger.info(f"✅ Producer démarré sur topic '{self.topic}'")
            logger.info(f"📡 Bootstrap servers: {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"❌ Erreur démarrage producer: {e}")
            raise
    
    def send_explanation(self, explanation: Dict[str, Any]) -> None:
        """
        Envoie une explication dans le topic Kafka
        
        Args:
            explanation: Dictionnaire contenant l'explication LLM
        """
        if not self.producer:
            self.start()
        
        try:
            alert_id = explanation.get('alert_id', 'unknown')
            
            # Envoyer le message
            future = self.producer.send(self.topic, explanation)
            
            # Attendre confirmation
            record_metadata = future.get(timeout=10)
            
            logger.info(
                f"✅ Explication envoyée | Alert: {alert_id} | "
                f"Topic: {record_metadata.topic} | "
                f"Partition: {record_metadata.partition} | "
                f"Offset: {record_metadata.offset}"
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi explication: {e}")
            raise
    
    def flush(self) -> None:
        """Force l'envoi de tous les messages en attente"""
        if self.producer:
            self.producer.flush()
            logger.debug("📤 Messages flushed")
    
    def close(self) -> None:
        """Ferme proprement le producer"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("🔌 Producer fermé")


if __name__ == "__main__":
    # Test du producer
    from datetime import datetime
    
    producer = ExplanationProducer()
    
    # Exemple d'explication
    test_explanation = {
        "alert_id": "test_flow_001",
        "timestamp": datetime.now().isoformat(),
        "explanation": {
            "summary": "Test d'explication LLM",
            "analysis": "Analyse technique détaillée...",
            "impact": "Impact potentiel sur le système...",
            "recommendations": [
                "Action 1",
                "Action 2",
                "Action 3"
            ],
            "priority": "P2"
        },
        "alert_level": "MEDIUM",
        "llm_model": "test-model",
        "processing_time_ms": 100.5
    }
    
    try:
        producer.send_explanation(test_explanation)
        print("✅ Explication test envoyée avec succès!")
    except Exception as e:
        print(f"❌ Erreur: {e}")
    finally:
        producer.close()
