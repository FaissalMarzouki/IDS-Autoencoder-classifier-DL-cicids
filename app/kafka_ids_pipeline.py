#!/usr/bin/env python3
"""
Kafka IDS Pipeline
Pipeline de detection d'intrusions en temps reel avec Apache Kafka

TOPICS KAFKA:
- ids-raw-data: Donnees brutes de trafic reseau (input)
- ids-features: Features extraites (intermediaire)
- ids-alerts: Alertes de detection (output)
- ids-explanations: Explications detaillees (output)

MODES:
- producer: Envoie des flux depuis le dataset vers Kafka
- consumer: Consomme les flux et effectue les predictions
- simulation: Mode local sans Kafka pour tester
"""

import argparse
import json
import time
import sys
import os
from datetime import datetime
from typing import Optional

# Ajouter le repertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from predictor import IDSPredictor, PredictionResult
from traffic_simulator import TrafficSimulator, NetworkFlow
from metrics_tracker import MetricsTracker


# Configuration par defaut
KAFKA_CONFIG = {
    'bootstrap_servers': 'localhost:9092',
    'topics': {
        'raw_data': 'ids-raw-data',
        'features': 'ids-features',
        'alerts': 'ids-alerts',
        'explanations': 'ids-explanations'
    }
}


def create_alert_message(flow: NetworkFlow, prediction: PredictionResult) -> dict:
    """Cree un message d'alerte pour Kafka"""
    return {
        'timestamp': datetime.now().isoformat(),
        'flow_id': flow.flow_id,
        'alert_type': prediction.predicted_class,
        'is_attack': prediction.is_attack,
        'confidence': prediction.confidence,
        'anomaly_score': prediction.anomaly_score,
        'true_label': flow.label,
        'correct': prediction.predicted_class == flow.label
    }


def create_explanation_message(flow: NetworkFlow, prediction: PredictionResult) -> dict:
    """Cree un message d'explication detaille"""
    return {
        'timestamp': datetime.now().isoformat(),
        'flow_id': flow.flow_id,
        'prediction': prediction.to_dict(),
        'true_label': flow.label,
        'analysis': {
            'is_correct': prediction.predicted_class == flow.label,
            'top_3_classes': sorted(
                prediction.all_probabilities.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
        }
    }


class KafkaIDSProducer:
    """Producteur Kafka pour les donnees IDS"""
    
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        try:
            from kafka import KafkaProducer
            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            self.enabled = True
            print(f"[OK] Connecte a Kafka: {bootstrap_servers}")
        except Exception as e:
            print(f"[WARN] Kafka non disponible: {e}")
            self.producer = None
            self.enabled = False
    
    def send(self, topic: str, message: dict):
        """Envoie un message vers un topic"""
        if self.producer:
            self.producer.send(topic, message)
    
    def flush(self):
        if self.producer:
            self.producer.flush()
    
    def close(self):
        if self.producer:
            self.producer.close()


class KafkaIDSConsumer:
    """Consommateur Kafka pour les donnees IDS"""
    
    def __init__(self, topic: str, bootstrap_servers: str = 'localhost:9092',
                 group_id: str = 'ids-consumer-group'):
        try:
            from kafka import KafkaConsumer
            self.consumer = KafkaConsumer(
                topic,
                bootstrap_servers=bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest'
            )
            self.enabled = True
            print(f"[OK] Consommateur Kafka connecte: {topic}")
        except Exception as e:
            print(f"[WARN] Kafka non disponible: {e}")
            self.consumer = None
            self.enabled = False
    
    def consume(self):
        """Generateur de messages"""
        if self.consumer:
            for message in self.consumer:
                yield message.value
    
    def close(self):
        if self.consumer:
            self.consumer.close()


def run_producer_mode(simulator: TrafficSimulator, count: int, 
                      attack_ratio: float, delay: float):
    """Mode producteur: envoie des flux vers Kafka"""
    
    producer = KafkaIDSProducer(KAFKA_CONFIG['bootstrap_servers'])
    
    print(f"\n[PRODUCER] Envoi de {count} flux vers Kafka...")
    print(f"  - Topic: {KAFKA_CONFIG['topics']['raw_data']}")
    print(f"  - Attack ratio: {attack_ratio:.0%}")
    print(f"  - Delay: {delay}s\n")
    
    for i, flow in enumerate(simulator.generate_stream(count, attack_ratio)):
        message = flow.to_dict()
        producer.send(KAFKA_CONFIG['topics']['raw_data'], message)
        
        if (i + 1) % 100 == 0:
            print(f"  Envoye: {i + 1}/{count}")
        
        if delay > 0:
            time.sleep(delay)
    
    producer.flush()
    producer.close()
    print(f"\n[OK] {count} flux envoyes vers Kafka")


def run_consumer_mode(predictor: IDSPredictor, tracker: MetricsTracker):
    """Mode consommateur: recoit et analyse les flux depuis Kafka"""
    
    consumer = KafkaIDSConsumer(
        KAFKA_CONFIG['topics']['raw_data'],
        KAFKA_CONFIG['bootstrap_servers']
    )
    
    producer = KafkaIDSProducer(KAFKA_CONFIG['bootstrap_servers'])
    
    print(f"\n[CONSUMER] En attente de flux depuis Kafka...")
    print(f"  - Input: {KAFKA_CONFIG['topics']['raw_data']}")
    print(f"  - Alerts: {KAFKA_CONFIG['topics']['alerts']}")
    print("  - Ctrl+C pour arreter\n")
    
    try:
        for message in consumer.consume():
            # Reconstruire le flow
            flow = NetworkFlow(
                flow_id=message['flow_id'],
                features=message['features'],
                label=message['label'],
                timestamp=message['timestamp']
            )
            
            # Prediction
            prediction = predictor.predict(flow.features, flow.flow_id)
            
            # Tracking
            tracker.update(
                flow.label,
                prediction.predicted_class,
                prediction.confidence,
                prediction.anomaly_score
            )
            
            # Envoyer alerte si attaque
            if prediction.is_attack:
                alert = create_alert_message(flow, prediction)
                producer.send(KAFKA_CONFIG['topics']['alerts'], alert)
            
            # Envoyer explication
            explanation = create_explanation_message(flow, prediction)
            producer.send(KAFKA_CONFIG['topics']['explanations'], explanation)
            
            # Affichage
            status = "OK" if prediction.predicted_class == flow.label else "MISS"
            print(f"[{status}] {flow.label:15} -> {prediction.predicted_class:15} ({prediction.confidence:.1%})")
    
    except KeyboardInterrupt:
        print("\n\n[STOP] Arret demande")
    
    finally:
        consumer.close()
        producer.close()
        tracker.print_summary()


def run_simulation_mode(predictor: IDSPredictor, simulator: TrafficSimulator,
                        tracker: MetricsTracker, count: int, attack_ratio: float,
                        verbose: bool = True, save_report: bool = True):
    """Mode simulation: test local sans Kafka"""
    
    print(f"\n[SIMULATION] Test de {count} flux sans Kafka")
    print(f"  - Attack ratio: {attack_ratio:.0%}")
    print(f"  - Verbose: {verbose}\n")
    
    correct = 0
    attacks_detected = 0
    
    for i, flow in enumerate(simulator.generate_stream(count, attack_ratio)):
        # Prediction
        prediction = predictor.predict(flow.features, flow.flow_id)
        
        # Tracking
        tracker.update(
            flow.label,
            prediction.predicted_class,
            prediction.confidence,
            prediction.anomaly_score
        )
        
        is_correct = prediction.predicted_class == flow.label
        if is_correct:
            correct += 1
        
        if prediction.is_attack:
            attacks_detected += 1
        
        # Affichage
        if verbose:
            status = "OK" if is_correct else "XX"
            print(f"[{status}] True: {flow.label:15} | Pred: {prediction.predicted_class:15} | Conf: {prediction.confidence:.1%}")
        elif (i + 1) % 100 == 0:
            print(f"  Traite: {i + 1}/{count} (Accuracy: {correct/(i+1):.1%})")
    
    # Rapport final
    tracker.print_summary()
    
    # Sauvegarder le rapport
    if save_report:
        report = tracker.get_report()
        report_path = f"metrics/simulation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs('metrics', exist_ok=True)
        with open(report_path, 'w') as f:
            f.write(report.to_json())
        print(f"\n[OK] Rapport sauvegarde: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Pipeline IDS avec Kafka',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Simulation locale (sans Kafka)
  python kafka_ids_pipeline.py --mode simulation --count 500

  # Producteur Kafka
  python kafka_ids_pipeline.py --mode producer --count 1000 --attack-ratio 0.3

  # Consommateur Kafka
  python kafka_ids_pipeline.py --mode consumer
        """
    )
    
    parser.add_argument('--mode', choices=['producer', 'consumer', 'simulation'],
                        default='simulation', help='Mode de fonctionnement')
    parser.add_argument('--count', type=int, default=100,
                        help='Nombre de flux a traiter')
    parser.add_argument('--attack-ratio', type=float, default=0.3,
                        help='Ratio d\'attaques (0.0 a 1.0)')
    parser.add_argument('--delay', type=float, default=0.0,
                        help='Delai entre les messages (secondes)')
    parser.add_argument('--models-dir', default='../models',
                        help='Repertoire des modeles')
    parser.add_argument('--dataset', default='../dataset/cicids2017_cleaned.csv',
                        help='Chemin vers le dataset')
    parser.add_argument('--kafka-server', default='localhost:9092',
                        help='Adresse du serveur Kafka')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Affichage detaille')
    parser.add_argument('--no-save', action='store_true',
                        help='Ne pas sauvegarder le rapport')
    
    args = parser.parse_args()
    
    # Mise a jour config Kafka
    KAFKA_CONFIG['bootstrap_servers'] = args.kafka_server
    
    print("="*60)
    print("IDS KAFKA PIPELINE")
    print("="*60)
    
    # Charger le modele
    print("\nChargement du modele...")
    predictor = IDSPredictor(args.models_dir)
    print(f"  - Classes: {predictor.class_names}")
    print(f"  - Features: {len(predictor.feature_names)}")
    
    # Charger le simulateur
    print("\nChargement du dataset...")
    simulator = TrafficSimulator(args.dataset)
    print(f"  - Flux disponibles: {len(simulator.df)}")
    print(f"  - Types d'attaques: {len(simulator.attack_types)}")
    
    # Tracker de metriques
    tracker = MetricsTracker(predictor.class_names)
    
    # Lancer le mode choisi
    if args.mode == 'producer':
        run_producer_mode(simulator, args.count, args.attack_ratio, args.delay)
    
    elif args.mode == 'consumer':
        run_consumer_mode(predictor, tracker)
    
    elif args.mode == 'simulation':
        run_simulation_mode(
            predictor, simulator, tracker,
            args.count, args.attack_ratio,
            args.verbose, not args.no_save
        )


if __name__ == '__main__':
    main()
