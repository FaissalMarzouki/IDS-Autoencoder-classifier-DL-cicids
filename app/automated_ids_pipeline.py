#!/usr/bin/env python3
"""
Pipeline IDS Automatisé avec Kafka
Simule le flux complet de surveillance réseau
"""

import json
import time
import threading
from datetime import datetime
from typing import Optional
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

from predictor import IDSPredictor
from traffic_simulator import TrafficSimulator, NetworkFlow


class DataPreprocessor:
    """Préprocesseur de données - transforme raw-data en features"""
    
    def __init__(self, bootstrap_servers: str = 'localhost:9093'):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=30000,
            max_block_ms=30000
        )
        self.consumer = KafkaConsumer(
            'ids-raw-data',
            bootstrap_servers=bootstrap_servers,
            group_id='preprocessor-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            session_timeout_ms=30000
        )
        print("[DataPreprocessor] Connecté à Kafka")
    
    def process_flow(self, raw_data: dict) -> dict:
        """Transforme les données brutes en features"""
        return {
            'flow_id': raw_data['flow_id'],
            'features': raw_data['features'],
            'label': raw_data['label'],
            'timestamp': raw_data['timestamp'],
            'preprocessed_at': datetime.now().isoformat()
        }
    
    def run(self):
        """Boucle principale du préprocesseur"""
        print("[DataPreprocessor] En attente de données brutes...")
        
        try:
            for message in self.consumer:
                raw_data = message.value
                
                # Préprocessing
                features_data = self.process_flow(raw_data)
                
                # Envoi vers ids-features
                self.producer.send('ids-features', features_data)
                
                print(f"[DataPreprocessor] ✓ {raw_data['flow_id']} → ids-features")
        
        except KeyboardInterrupt:
            print("\n[DataPreprocessor] Arrêt...")
        finally:
            self.consumer.close()
            self.producer.close()


class ThreatDetector:
    """Détecteur de menaces - applique le modèle IDS"""
    
    def __init__(self, models_dir: str = '../models', 
                 bootstrap_servers: str = 'localhost:9093'):
        # Charger le modèle IDS
        self.predictor = IDSPredictor(models_dir)
        print(f"[ThreatDetector] Modèle chargé: {len(self.predictor.class_names)} classes")
        
        # Kafka
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=30000,
            max_block_ms=30000
        )
        self.consumer = KafkaConsumer(
            'ids-features',
            bootstrap_servers=bootstrap_servers,
            group_id='detector-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            session_timeout_ms=30000
        )
        print("[ThreatDetector] Connecté à Kafka")
    
    def detect(self, features_data: dict):
        """Détecte les menaces et publie uniquement les alertes"""
        # Prédiction
        prediction = self.predictor.predict(
            features_data['features'],
            features_data['flow_id']
        )
        
        # Envoyer l'alerte UNIQUEMENT si attaque détectée
        if prediction.is_attack:
            alert = {
                'timestamp': datetime.now().isoformat(),
                'flow_id': features_data['flow_id'],
                'alert_type': prediction.predicted_class,
                'confidence': prediction.confidence,
                'anomaly_score': prediction.anomaly_score,
                'severity': self._calculate_severity(prediction),
                'true_label': features_data['label'],
                'correct': prediction.predicted_class == features_data['label'],
                # Informations supplémentaires pour le LLM Explainer
                'all_probabilities': prediction.all_probabilities,
                'top_3_classes': sorted(
                    prediction.all_probabilities.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3],
                'features_summary': {
                    'preprocessed_at': features_data.get('preprocessed_at'),
                    'original_timestamp': features_data.get('timestamp')
                }
            }
            self.producer.send('ids-alerts', alert)
            print(f"[ThreatDetector] 🚨 ALERTE: {prediction.predicted_class} (conf: {prediction.confidence:.1%})")
        else:
            # Trafic normal - pas d'alerte
            print(f"[ThreatDetector] ✓ Trafic normal détecté (conf: {prediction.confidence:.1%})")
    
    def _calculate_severity(self, prediction) -> str:
        """Calcule la sévérité de l'alerte"""
        if prediction.confidence >= 0.9:
            return "CRITIQUE"
        elif prediction.confidence >= 0.7:
            return "ÉLEVÉE"
        elif prediction.confidence >= 0.5:
            return "MOYENNE"
        else:
            return "FAIBLE"
    
    def run(self):
        """Boucle principale du détecteur"""
        print("[ThreatDetector] En attente de features...")
        
        try:
            for message in self.consumer:
                features_data = message.value
                self.detect(features_data)
        
        except KeyboardInterrupt:
            print("\n[ThreatDetector] Arrêt...")
        finally:
            self.consumer.close()
            self.producer.close()


class AlertMonitor:
    """Moniteur d'alertes - affiche les alertes en temps réel"""
    
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        self.consumer = KafkaConsumer(
            'ids-alerts',
            bootstrap_servers=bootstrap_servers,
            group_id='monitor-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest'
        )
        print("[AlertMonitor] Connecté à Kafka")
        
        # Statistiques
        self.total_alerts = 0
        self.alerts_by_type = {}
        self.start_time = time.time()
    
    def display_alert(self, alert: dict):
        """Affiche une alerte formatée"""
        severity = alert.get('severity', 'INCONNUE')
        
        # Couleurs selon la sévérité
        colors = {
            'CRITIQUE': '\033[91m',  # Rouge
            'ÉLEVÉE': '\033[93m',     # Jaune
            'MOYENNE': '\033[94m',    # Bleu
            'FAIBLE': '\033[92m'      # Vert
        }
        reset = '\033[0m'
        
        color = colors.get(severity, '')
        
        print("\n" + "="*70)
        print(f"{color}🚨 ALERTE SÉCURITÉ - Sévérité: {severity}{reset}")
        print("="*70)
        print(f"  Horodatage:     {alert['timestamp']}")
        print(f"  Flow ID:        {alert['flow_id']}")
        print(f"  Type d'attaque: {alert['alert_type']}")
        print(f"  Confiance:      {alert['confidence']:.1%}")
        print(f"  Score anomalie: {alert['anomaly_score']:.6f}")
        print(f"  Label réel:     {alert['true_label']}")
        print(f"  Prédiction:     {'✓ CORRECTE' if alert['correct'] else '✗ INCORRECTE'}")
        print("="*70)
        
        # Mise à jour stats
        self.total_alerts += 1
        attack_type = alert['alert_type']
        self.alerts_by_type[attack_type] = self.alerts_by_type.get(attack_type, 0) + 1
    
    def print_stats(self):
        """Affiche les statistiques"""
        elapsed = time.time() - self.start_time
        print("\n" + "="*70)
        print("📊 STATISTIQUES DE SURVEILLANCE")
        print("="*70)
        print(f"  Durée:          {elapsed:.1f}s")
        print(f"  Total alertes:  {self.total_alerts}")
        print(f"  Taux:           {self.total_alerts / elapsed:.2f} alertes/s")
        print("\n  Répartition par type:")
        for attack_type, count in sorted(self.alerts_by_type.items(), 
                                         key=lambda x: x[1], reverse=True):
            print(f"    - {attack_type:20}: {count:4} ({count/self.total_alerts*100:.1f}%)")
        print("="*70)
    
    def run(self):
        """Boucle principale du moniteur"""
        print("[AlertMonitor] Surveillance des alertes en cours...")
        print("  (Ctrl+C pour arrêter et voir les statistiques)\n")
        
        try:
            for message in self.consumer:
                alert = message.value
                self.display_alert(alert)
        
        except KeyboardInterrupt:
            print("\n\n[AlertMonitor] Arrêt...")
            self.print_stats()
        finally:
            self.consumer.close()


class TrafficProducer:
    """Producteur de trafic réseau depuis le dataset"""
    
    def __init__(self, dataset_path: str = '../dataset/cicids2017_cleaned.csv',
                 bootstrap_servers: str = 'localhost:9093'):
        self.simulator = TrafficSimulator(dataset_path)
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=30000,
            max_block_ms=30000
        )
        print(f"[TrafficProducer] Dataset chargé: {len(self.simulator.df)} flux")
    
    def run(self, count: int = 1000, attack_ratio: float = 0.3, 
            delay: float = 0.1):
        """Génère et envoie du trafic réseau"""
        print(f"[TrafficProducer] Envoi de {count} flux (attack_ratio={attack_ratio:.0%}, delay={delay}s)")
        
        try:
            for i, flow in enumerate(self.simulator.generate_stream(count, attack_ratio)):
                # Envoyer vers ids-raw-data
                self.producer.send('ids-raw-data', flow.to_dict())
                
                if (i + 1) % 100 == 0:
                    print(f"[TrafficProducer] Envoyé: {i + 1}/{count}")
                
                time.sleep(delay)
            
            self.producer.flush()
            print(f"[TrafficProducer] ✓ {count} flux envoyés")
        
        except KeyboardInterrupt:
            print("\n[TrafficProducer] Arrêt...")
        finally:
            self.producer.close()


def run_pipeline(count: int = 1000, attack_ratio: float = 0.3, 
                 delay: float = 0.1, dataset_path: str = '../dataset/cicids2017_cleaned.csv',
                 kafka_server: str = 'localhost:9093'):
    """Lance le pipeline complet"""
    
    print("\n" + "="*70)
    print("🚀 LANCEMENT DU PIPELINE IDS KAFKA")
    print("="*70)
    print(f"  Flux à traiter:  {count}")
    print(f"  Ratio d'attaque: {attack_ratio:.0%}")
    print(f"  Délai:           {delay}s")
    print(f"  Kafka:           {kafka_server}")
    print("="*70 + "\n")
    
    # Démarrer les composants dans des threads
    threads = []
    
    # 1. DataPreprocessor
    preprocessor = DataPreprocessor(kafka_server)
    t1 = threading.Thread(target=preprocessor.run, daemon=True)
    t1.start()
    threads.append(t1)
    time.sleep(1)
    
    # 2. ThreatDetector
    detector = ThreatDetector(bootstrap_servers=kafka_server)
    t2 = threading.Thread(target=detector.run, daemon=True)
    t2.start()
    threads.append(t2)
    time.sleep(1)
    
    # 3. AlertMonitor
    monitor = AlertMonitor(kafka_server)
    t3 = threading.Thread(target=monitor.run, daemon=True)
    t3.start()
    threads.append(t3)
    time.sleep(1)
    
    print("\n[PIPELINE] Tous les composants sont démarrés ✓\n")
    time.sleep(2)
    
    # 4. Démarrer le producteur (génération de trafic)
    producer = TrafficProducer(dataset_path, kafka_server)
    producer.run(count, attack_ratio, delay)
    
    # Attendre un peu pour que tout soit traité
    print("\n[PIPELINE] Attente du traitement final...")
    time.sleep(5)
    
    print("\n[PIPELINE] Pipeline terminé ✓")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Pipeline IDS automatisé avec Kafka')
    parser.add_argument('--count', type=int, default=1000,
                        help='Nombre de flux à traiter')
    parser.add_argument('--attack-ratio', type=float, default=0.3,
                        help='Proportion d\'attaques (0.0-1.0)')
    parser.add_argument('--delay', type=float, default=0.1,
                        help='Délai entre les flux (secondes)')
    parser.add_argument('--dataset', default='../dataset/cicids2017_cleaned.csv',
                        help='Chemin vers le dataset CSV')
    parser.add_argument('--kafka-server', default='localhost:9093',
                        help='Adresse du serveur Kafka (défaut: localhost:9093)')
    
    args = parser.parse_args()
    
    try:
        run_pipeline(
            count=args.count,
            attack_ratio=args.attack_ratio,
            delay=args.delay,
            dataset_path=args.dataset,
            kafka_server=args.kafka_server
        )
    except KeyboardInterrupt:
        print("\n\n[PIPELINE] Arrêt du pipeline")