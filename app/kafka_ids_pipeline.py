# ============================================================================
# KAFKA_IDS_PIPELINE.PY - Pipeline Kafka pour l'IDS en temps réel
# ============================================================================
"""
Pipeline Kafka pour le système IDS.
Consomme les flux depuis ids-raw-data, effectue des prédictions,
et publie les résultats sur ids-alerts et ids-explanations.

Topics Kafka:
- ids-raw-data: Flux réseau bruts (entrée)
- ids-features: Features extraites (intermédiaire)
- ids-alerts: Alertes de détection (sortie)
- ids-explanations: Explications détaillées (sortie)

Usage:
    python kafka_ids_pipeline.py --mode consumer
    python kafka_ids_pipeline.py --mode producer --count 1000
    python kafka_ids_pipeline.py --mode full --count 500
"""

import json
import argparse
import time
import signal
import sys
from datetime import datetime
from typing import Optional
import numpy as np

# Kafka
try:
    from kafka import KafkaProducer, KafkaConsumer
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    print("⚠️ kafka-python non installé. Installer avec: pip install kafka-python")

# Modules locaux
from predictor import IDSPredictor, PredictionResult
from traffic_simulator import TrafficSimulator, SimulatedFlow
from metrics_tracker import MetricsTracker
from config import KAFKA_CONFIG, MODEL_CONFIG, SIMULATION_CONFIG


# ============================================================================
# PRODUCTEUR KAFKA (Simule le trafic réseau)
# ============================================================================

class IDSKafkaProducer:
    """
    Producteur Kafka qui simule du trafic réseau.
    Lit le dataset et publie des flux sur le topic ids-raw-data.
    """
    
    def __init__(
        self, 
        bootstrap_servers: str = KAFKA_CONFIG.bootstrap_servers,
        topic: str = KAFKA_CONFIG.topic_raw_data
    ):
        self.topic = topic
        self.simulator = None
        
        if not KAFKA_AVAILABLE:
            raise ImportError("kafka-python requis")
        
        print(f"🔌 Connexion au broker Kafka: {bootstrap_servers}")
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks=KAFKA_CONFIG.acks,
            retries=KAFKA_CONFIG.retries
        )
        print(f"✅ Producteur connecté au topic: {topic}")
    
    def load_simulator(self, dataset_path: str = SIMULATION_CONFIG.dataset_path):
        """Charge le simulateur de trafic."""
        self.simulator = TrafficSimulator(dataset_path)
    
    def send_flow(self, flow: SimulatedFlow):
        """Envoie un flux sur Kafka."""
        message = {
            "flow_id": flow.flow_id,
            "features": flow.features.tolist(),
            "true_label": flow.label,
            "timestamp": datetime.now().isoformat()
        }
        
        future = self.producer.send(self.topic, message)
        future.get(timeout=10)  # Attendre confirmation
    
    def produce_flows(
        self, 
        count: int, 
        delay: float = 0.1,
        attack_type: Optional[str] = None
    ):
        """
        Produit des flux vers Kafka.
        
        Args:
            count: Nombre de flux à produire
            delay: Délai entre chaque flux (secondes)
            attack_type: Type d'attaque spécifique (None = mélangé)
        """
        if self.simulator is None:
            self.load_simulator()
        
        print(f"\n📤 Production de {count} flux vers {self.topic}...")
        
        for i in range(count):
            flow = self.simulator.get_random_flow(attack_type)
            self.send_flow(flow)
            
            if (i + 1) % 100 == 0:
                print(f"   Envoyés: {i + 1}/{count}")
            
            if delay > 0:
                time.sleep(delay)
        
        self.producer.flush()
        print(f"✅ {count} flux envoyés!")
    
    def close(self):
        """Ferme la connexion."""
        self.producer.close()


# ============================================================================
# CONSOMMATEUR KAFKA (Traite les flux avec l'IDS)
# ============================================================================

class IDSKafkaConsumer:
    """
    Consommateur Kafka qui traite les flux avec le modèle IDS.
    Consomme depuis ids-raw-data et publie vers ids-alerts.
    """
    
    def __init__(
        self,
        bootstrap_servers: str = KAFKA_CONFIG.bootstrap_servers,
        input_topic: str = KAFKA_CONFIG.topic_raw_data,
        alerts_topic: str = KAFKA_CONFIG.topic_alerts,
        explanations_topic: str = KAFKA_CONFIG.topic_explanations,
        group_id: str = KAFKA_CONFIG.consumer_group_id
    ):
        self.input_topic = input_topic
        self.alerts_topic = alerts_topic
        self.explanations_topic = explanations_topic
        self.running = False
        
        if not KAFKA_AVAILABLE:
            raise ImportError("kafka-python requis")
        
        # Charger le modèle IDS
        print(f"🧠 Chargement du modèle IDS...")
        self.predictor = IDSPredictor(MODEL_CONFIG.models_dir)
        
        # Tracker de métriques
        self.metrics = MetricsTracker(self.predictor.class_names)
        
        # Consumer Kafka
        print(f"🔌 Connexion au broker Kafka: {bootstrap_servers}")
        self.consumer = KafkaConsumer(
            input_topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset=KAFKA_CONFIG.auto_offset_reset,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        # Producer pour les alertes
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        print(f"✅ Consommateur prêt!")
        print(f"   • Input: {input_topic}")
        print(f"   • Alerts: {alerts_topic}")
        print(f"   • Explanations: {explanations_topic}")
    
    def process_message(self, message) -> Optional[PredictionResult]:
        """Traite un message Kafka."""
        data = message.value
        
        # Extraire les features
        features = np.array(data['features'], dtype=np.float32)
        flow_id = data.get('flow_id', 'unknown')
        true_label = data.get('true_label')
        
        # Prédiction
        result = self.predictor.predict(features, flow_id)
        
        # Mise à jour des métriques si on a le vrai label
        if true_label:
            self.metrics.update(
                true_label=true_label,
                predicted_label=result.predicted_class,
                confidence=result.confidence,
                anomaly_score=result.anomaly_score,
                flow_id=flow_id
            )
        
        return result, true_label
    
    def publish_alert(self, result: PredictionResult, true_label: Optional[str] = None):
        """Publie une alerte si nécessaire."""
        # Créer le message d'alerte
        alert = {
            "flow_id": result.flow_id,
            "timestamp": result.timestamp,
            "alert_type": "ATTACK_DETECTED" if result.is_attack else "NORMAL",
            "predicted_class": result.predicted_class,
            "confidence": result.confidence,
            "anomaly_score": result.anomaly_score,
            "is_anomaly": result.is_anomaly
        }
        
        # Ajouter le vrai label si disponible (pour évaluation)
        if true_label:
            alert["true_label"] = true_label
            alert["is_correct"] = (true_label == result.predicted_class)
        
        # Publier sur le topic alerts
        self.producer.send(self.alerts_topic, alert)
        
        # Si c'est une attaque, publier aussi l'explication
        if result.is_attack or result.is_anomaly:
            explanation = {
                "flow_id": result.flow_id,
                "timestamp": result.timestamp,
                "explanation": {
                    "predicted_class": result.predicted_class,
                    "confidence": result.confidence,
                    "all_probabilities": result.all_probabilities,
                    "reconstruction_error": result.reconstruction_error,
                    "anomaly_score": result.anomaly_score,
                    "reason": self._generate_explanation(result)
                }
            }
            self.producer.send(self.explanations_topic, explanation)
    
    def _generate_explanation(self, result: PredictionResult) -> str:
        """Génère une explication textuelle."""
        reasons = []
        
        if result.is_attack:
            reasons.append(f"Attaque de type '{result.predicted_class}' détectée avec {result.confidence:.1%} de confiance")
        
        if result.is_anomaly:
            reasons.append(f"Comportement anormal détecté (score anomalie: {result.anomaly_score:.2f})")
        
        # Top 3 probabilités
        sorted_probs = sorted(result.all_probabilities.items(), key=lambda x: x[1], reverse=True)[:3]
        probs_str = ", ".join([f"{k}: {v:.1%}" for k, v in sorted_probs])
        reasons.append(f"Top probabilités: {probs_str}")
        
        return " | ".join(reasons)
    
    def consume(self, max_messages: Optional[int] = None, print_interval: int = 100):
        """
        Consomme et traite les messages.
        
        Args:
            max_messages: Nombre max de messages (None = infini)
            print_interval: Intervalle d'affichage des stats
        """
        self.running = True
        count = 0
        
        print(f"\n🎯 Démarrage de la consommation...")
        print(f"   (Ctrl+C pour arrêter)\n")
        
        try:
            for message in self.consumer:
                if not self.running:
                    break
                
                # Traiter le message
                result, true_label = self.process_message(message)
                
                # Publier l'alerte
                self.publish_alert(result, true_label)
                
                count += 1
                
                # Affichage périodique
                if count % print_interval == 0:
                    self._print_status(count, result)
                
                # Limite atteinte?
                if max_messages and count >= max_messages:
                    break
            
        except KeyboardInterrupt:
            print("\n⚠️ Interruption utilisateur")
        
        finally:
            self.producer.flush()
            self._print_final_report(count)
    
    def _print_status(self, count: int, last_result: PredictionResult):
        """Affiche le statut actuel."""
        report = self.metrics.get_report()
        attack = report['attack_detection']
        
        status = "🚨 ATTAQUE" if last_result.is_attack else "✅ Normal"
        
        print(f"[{count:,}] {status} | "
              f"Classe: {last_result.predicted_class} ({last_result.confidence:.1%}) | "
              f"Acc: {report['summary']['overall_accuracy']:.1%} | "
              f"FP: {attack['false_positives']} | FN: {attack['false_negatives']}")
    
    def _print_final_report(self, total_processed: int):
        """Affiche le rapport final."""
        print(f"\n{'='*70}")
        print(f"📊 RAPPORT FINAL - {total_processed:,} flux traités")
        print(f"{'='*70}")
        
        self.metrics.print_report()
        
        # Sauvegarder le rapport
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"./metrics/kafka_report_{timestamp}.json"
        
        import os
        os.makedirs("./metrics", exist_ok=True)
        self.metrics.save_report(report_path)
    
    def stop(self):
        """Arrête le consommateur."""
        self.running = False
    
    def close(self):
        """Ferme les connexions."""
        self.consumer.close()
        self.producer.close()


# ============================================================================
# MODE SIMULATION (Sans Kafka - pour tests locaux)
# ============================================================================

def run_simulation_mode(count: int = 1000, dataset_path: str = SIMULATION_CONFIG.dataset_path):
    """
    Mode simulation sans Kafka - pour tester localement.
    
    Args:
        count: Nombre de flux à traiter
        dataset_path: Chemin vers le dataset
    """
    print("=" * 70)
    print("🧪 MODE SIMULATION (sans Kafka)")
    print("=" * 70)
    
    # Charger les composants
    predictor = IDSPredictor(MODEL_CONFIG.models_dir)
    simulator = TrafficSimulator(dataset_path)
    metrics = MetricsTracker(predictor.class_names)
    
    print(f"\n📊 Traitement de {count:,} flux...")
    
    start_time = time.time()
    
    for i in range(count):
        # Obtenir un flux
        flow = simulator.get_random_flow()
        
        # Prédiction
        result = predictor.predict(flow.features, flow.flow_id)
        
        # Mise à jour des métriques
        metrics.update(
            true_label=flow.label,
            predicted_label=result.predicted_class,
            confidence=result.confidence,
            anomaly_score=result.anomaly_score,
            flow_id=flow.flow_id
        )
        
        # Affichage périodique
        if (i + 1) % 200 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            report = metrics.get_report()
            print(f"[{i+1:,}/{count:,}] "
                  f"Acc: {report['summary']['overall_accuracy']:.2%} | "
                  f"FP: {report['attack_detection']['false_positives']} | "
                  f"FN: {report['attack_detection']['false_negatives']} | "
                  f"Rate: {rate:.0f} flux/s")
    
    # Rapport final
    elapsed = time.time() - start_time
    print(f"\n⏱️ Temps total: {elapsed:.1f}s ({count/elapsed:.0f} flux/s)")
    
    metrics.print_report()
    
    # Sauvegarder
    import os
    os.makedirs("./metrics", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    metrics.save_report(f"./metrics/simulation_report_{timestamp}.json")
    
    # Afficher les erreurs récentes
    print("\n🔍 Dernières erreurs de prédiction:")
    errors = metrics.get_recent_errors(5)
    for err in errors:
        print(f"   • {err['flow_id']}: {err['true_label']} → {err['predicted_label']} "
              f"(conf: {err['confidence']:.1%})")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline IDS Kafka pour la détection d'intrusions en temps réel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Mode simulation (sans Kafka) - pour tests locaux
  python kafka_ids_pipeline.py --mode simulation --count 1000
  
  # Producteur: envoyer des flux vers Kafka
  python kafka_ids_pipeline.py --mode producer --count 500
  
  # Consommateur: traiter les flux depuis Kafka
  python kafka_ids_pipeline.py --mode consumer --max 1000
  
  # Pipeline complet: produire et consommer
  python kafka_ids_pipeline.py --mode full --count 500
        """
    )
    
    parser.add_argument(
        '--mode', 
        choices=['simulation', 'producer', 'consumer', 'full'],
        default='simulation',
        help='Mode d\'exécution'
    )
    
    parser.add_argument(
        '--count', 
        type=int, 
        default=1000,
        help='Nombre de flux à produire (modes: simulation, producer, full)'
    )
    
    parser.add_argument(
        '--max', 
        type=int, 
        default=None,
        help='Nombre max de messages à consommer (mode: consumer)'
    )
    
    parser.add_argument(
        '--delay', 
        type=float, 
        default=0.01,
        help='Délai entre les flux produits (secondes)'
    )
    
    parser.add_argument(
        '--bootstrap-servers', 
        default=KAFKA_CONFIG.bootstrap_servers,
        help='Serveurs Kafka (host:port)'
    )
    
    parser.add_argument(
        '--dataset', 
        default=SIMULATION_CONFIG.dataset_path,
        help='Chemin vers le dataset'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🛡️  IDS KAFKA PIPELINE - Détection d'Intrusions en Temps Réel")
    print("=" * 70)
    print(f"   Mode: {args.mode}")
    print(f"   Bootstrap servers: {args.bootstrap_servers}")
    print("=" * 70)
    
    try:
        if args.mode == 'simulation':
            run_simulation_mode(args.count, args.dataset)
        
        elif args.mode == 'producer':
            if not KAFKA_AVAILABLE:
                print("❌ kafka-python non disponible. Utiliser --mode simulation")
                sys.exit(1)
            
            producer = IDSKafkaProducer(args.bootstrap_servers)
            producer.load_simulator(args.dataset)
            producer.produce_flows(args.count, args.delay)
            producer.close()
        
        elif args.mode == 'consumer':
            if not KAFKA_AVAILABLE:
                print("❌ kafka-python non disponible. Utiliser --mode simulation")
                sys.exit(1)
            
            consumer = IDSKafkaConsumer(args.bootstrap_servers)
            
            # Gérer l'arrêt propre
            def signal_handler(sig, frame):
                print("\n⚠️ Signal d'arrêt reçu...")
                consumer.stop()
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            consumer.consume(args.max)
            consumer.close()
        
        elif args.mode == 'full':
            if not KAFKA_AVAILABLE:
                print("❌ kafka-python non disponible. Utiliser --mode simulation")
                sys.exit(1)
            
            import threading
            
            # Démarrer le consommateur dans un thread
            consumer = IDSKafkaConsumer(args.bootstrap_servers)
            consumer_thread = threading.Thread(
                target=consumer.consume,
                kwargs={'max_messages': args.count}
            )
            consumer_thread.start()
            
            # Attendre un peu que le consommateur soit prêt
            time.sleep(2)
            
            # Produire les flux
            producer = IDSKafkaProducer(args.bootstrap_servers)
            producer.load_simulator(args.dataset)
            producer.produce_flows(args.count, args.delay)
            producer.close()
            
            # Attendre le consommateur
            consumer_thread.join(timeout=30)
            consumer.close()
    
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
