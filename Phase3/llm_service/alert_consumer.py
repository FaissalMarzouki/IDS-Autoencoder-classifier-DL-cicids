"""
Consumer Kafka pour les alertes IDS
"""
from kafka import KafkaConsumer
import json
import logging
from typing import Generator, Dict, Any
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


class AlertConsumer:
    """Consumer Kafka pour lire les alertes depuis ids-alerts"""
    
    def __init__(self):
        self.topic = KAFKA_CONFIG['topics']['alerts']
        self.bootstrap_servers = KAFKA_CONFIG['bootstrap_servers']
        self.group_id = KAFKA_CONFIG['consumer_groups']['llm_service']
        self.consumer = None
        
    def start(self) -> None:
        """Initialise le consumer Kafka"""
        try:
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                **KAFKA_CONFIG['consumer_config']
            )
            logger.info(f"✅ Consumer démarré sur topic '{self.topic}'")
            logger.info(f"📡 Bootstrap servers: {self.bootstrap_servers}")
            logger.info(f"👥 Consumer group: {self.group_id}")
        except Exception as e:
            logger.error(f"❌ Erreur démarrage consumer: {e}")
            raise
    
    def consume(self) -> Generator[Dict[str, Any], None, None]:
        """
        Consomme les alertes en continu
        
        Yields:
            Dict contenant l'alerte IDS
        """
        if not self.consumer:
            self.start()
        
        logger.info("🔄 Début de la consommation des alertes...")
        
        try:
            for message in self.consumer:
                alert = message.value
                flow_id = alert.get('flow_id', 'unknown')
                predicted_class = alert.get('predicted_class', 'N/A')
                confidence = alert.get('confidence', 0.0)
                
                logger.info(
                    f"📨 Alerte reçue | Flow: {flow_id} | "
                    f"Classe: {predicted_class} | "
                    f"Confiance: {confidence:.2%}"
                )
                
                yield alert
                
        except KeyboardInterrupt:
            logger.info("⚠️ Interruption utilisateur")
            self.close()
        except Exception as e:
            logger.error(f"❌ Erreur consommation: {e}")
            raise
    
    def close(self) -> None:
        """Ferme proprement le consumer"""
        if self.consumer:
            self.consumer.close()
            logger.info("🔌 Consumer fermé")


if __name__ == "__main__":
    # Test du consumer
    consumer = AlertConsumer()
    
    try:
        for alert in consumer.consume():
            print(f"\n📋 Alerte reçue:")
            print(json.dumps(alert, indent=2, ensure_ascii=False))
            print("-" * 80)
    except KeyboardInterrupt:
        print("\n👋 Arrêt du consumer")
