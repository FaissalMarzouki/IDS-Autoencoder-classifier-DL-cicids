# ============================================================================
# METRICS_TRACKER.PY - Suivi des métriques FP, FN, TP, TN en temps réel
# ============================================================================
"""
Module de suivi des métriques de performance de l'IDS.
Calcule en temps réel: TP, TN, FP, FN, Precision, Recall, F1, etc.
"""

import numpy as np
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import json


@dataclass
class ConfusionMetrics:
    """Métriques de confusion pour une classe."""
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    
    @property
    def precision(self) -> float:
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)
    
    @property
    def recall(self) -> float:
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)
    
    @property
    def f1_score(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)
    
    @property
    def accuracy(self) -> float:
        total = self.true_positives + self.true_negatives + self.false_positives + self.false_negatives
        if total == 0:
            return 0.0
        return (self.true_positives + self.true_negatives) / total


class MetricsTracker:
    """
    Tracker de métriques en temps réel pour l'IDS.
    
    Usage:
        tracker = MetricsTracker(class_names=['Normal', 'DDoS', 'DoS'])
        tracker.update(true_label='DDoS', predicted_label='DDoS', confidence=0.95)
        report = tracker.get_report()
    """
    
    def __init__(self, class_names: List[str]):
        """
        Initialise le tracker.
        
        Args:
            class_names: Liste des noms de classes
        """
        self.class_names = class_names
        self.normal_class = "Normal Traffic"
        
        # Métriques par classe
        self.class_metrics: Dict[str, ConfusionMetrics] = {
            name: ConfusionMetrics() for name in class_names
        }
        
        # Métriques globales (attaque vs normal)
        self.global_metrics = ConfusionMetrics()
        
        # Historique détaillé
        self.predictions_history: List[Dict] = []
        
        # Matrice de confusion
        self.confusion_matrix = defaultdict(lambda: defaultdict(int))
        
        # Compteurs
        self.total_predictions = 0
        self.total_correct = 0
        
        # Timestamp de début
        self.start_time = datetime.now()
    
    def update(
        self, 
        true_label: str, 
        predicted_label: str, 
        confidence: float,
        anomaly_score: float = 0.0,
        flow_id: Optional[str] = None
    ):
        """
        Met à jour les métriques avec une nouvelle prédiction.
        
        Args:
            true_label: Label réel
            predicted_label: Label prédit
            confidence: Confiance de la prédiction
            anomaly_score: Score d'anomalie
            flow_id: ID du flux (optionnel)
        """
        self.total_predictions += 1
        is_correct = (true_label == predicted_label)
        
        if is_correct:
            self.total_correct += 1
        
        # Mise à jour de la matrice de confusion
        self.confusion_matrix[true_label][predicted_label] += 1
        
        # Déterminer si c'est une attaque
        true_is_attack = (true_label != self.normal_class)
        pred_is_attack = (predicted_label != self.normal_class)
        
        # Mise à jour des métriques globales (attack detection)
        if true_is_attack and pred_is_attack:
            self.global_metrics.true_positives += 1
        elif not true_is_attack and not pred_is_attack:
            self.global_metrics.true_negatives += 1
        elif not true_is_attack and pred_is_attack:
            self.global_metrics.false_positives += 1
        else:  # true_is_attack and not pred_is_attack
            self.global_metrics.false_negatives += 1
        
        # Mise à jour des métriques par classe
        for class_name in self.class_names:
            metrics = self.class_metrics[class_name]
            
            if true_label == class_name and predicted_label == class_name:
                metrics.true_positives += 1
            elif true_label != class_name and predicted_label != class_name:
                metrics.true_negatives += 1
            elif true_label != class_name and predicted_label == class_name:
                metrics.false_positives += 1
            else:  # true_label == class_name and predicted_label != class_name
                metrics.false_negatives += 1
        
        # Enregistrer dans l'historique
        self.predictions_history.append({
            "flow_id": flow_id,
            "true_label": true_label,
            "predicted_label": predicted_label,
            "is_correct": is_correct,
            "confidence": confidence,
            "anomaly_score": anomaly_score,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_overall_accuracy(self) -> float:
        """Retourne l'accuracy globale."""
        if self.total_predictions == 0:
            return 0.0
        return self.total_correct / self.total_predictions
    
    def get_attack_detection_rate(self) -> float:
        """Retourne le taux de détection des attaques (recall global)."""
        return self.global_metrics.recall
    
    def get_false_positive_rate(self) -> float:
        """Retourne le taux de faux positifs."""
        tn = self.global_metrics.true_negatives
        fp = self.global_metrics.false_positives
        if tn + fp == 0:
            return 0.0
        return fp / (tn + fp)
    
    def get_false_negative_rate(self) -> float:
        """Retourne le taux de faux négatifs."""
        tp = self.global_metrics.true_positives
        fn = self.global_metrics.false_negatives
        if tp + fn == 0:
            return 0.0
        return fn / (tp + fn)
    
    def get_class_report(self) -> Dict:
        """Retourne un rapport détaillé par classe."""
        report = {}
        for class_name, metrics in self.class_metrics.items():
            report[class_name] = {
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "true_positives": metrics.true_positives,
                "false_positives": metrics.false_positives,
                "false_negatives": metrics.false_negatives,
                "support": metrics.true_positives + metrics.false_negatives
            }
        return report
    
    def get_confusion_matrix_dict(self) -> Dict:
        """Retourne la matrice de confusion sous forme de dictionnaire."""
        return {
            true_label: dict(predictions) 
            for true_label, predictions in self.confusion_matrix.items()
        }
    
    def get_report(self) -> Dict:
        """Génère un rapport complet des métriques."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "summary": {
                "total_predictions": self.total_predictions,
                "total_correct": self.total_correct,
                "overall_accuracy": self.get_overall_accuracy(),
                "elapsed_seconds": elapsed,
                "predictions_per_second": self.total_predictions / elapsed if elapsed > 0 else 0
            },
            "attack_detection": {
                "true_positives": self.global_metrics.true_positives,
                "true_negatives": self.global_metrics.true_negatives,
                "false_positives": self.global_metrics.false_positives,
                "false_negatives": self.global_metrics.false_negatives,
                "precision": self.global_metrics.precision,
                "recall": self.global_metrics.recall,
                "f1_score": self.global_metrics.f1_score,
                "false_positive_rate": self.get_false_positive_rate(),
                "false_negative_rate": self.get_false_negative_rate()
            },
            "per_class": self.get_class_report(),
            "confusion_matrix": self.get_confusion_matrix_dict()
        }
    
    def print_report(self):
        """Affiche un rapport formaté."""
        report = self.get_report()
        
        print("\n" + "=" * 70)
        print("📊 RAPPORT DE MÉTRIQUES IDS")
        print("=" * 70)
        
        summary = report["summary"]
        print(f"\n📈 RÉSUMÉ:")
        print(f"   • Total prédictions: {summary['total_predictions']:,}")
        print(f"   • Prédictions correctes: {summary['total_correct']:,}")
        print(f"   • Accuracy globale: {summary['overall_accuracy']:.2%}")
        print(f"   • Durée: {summary['elapsed_seconds']:.1f}s")
        print(f"   • Débit: {summary['predictions_per_second']:.1f} pred/s")
        
        attack = report["attack_detection"]
        print(f"\n🛡️ DÉTECTION D'ATTAQUES:")
        print(f"   • True Positives (attaques détectées): {attack['true_positives']:,}")
        print(f"   • True Negatives (normal correct): {attack['true_negatives']:,}")
        print(f"   • False Positives (fausses alertes): {attack['false_positives']:,}")
        print(f"   • False Negatives (attaques manquées): {attack['false_negatives']:,}")
        print(f"   • Precision: {attack['precision']:.2%}")
        print(f"   • Recall (Detection Rate): {attack['recall']:.2%}")
        print(f"   • F1-Score: {attack['f1_score']:.2%}")
        print(f"   • Taux FP: {attack['false_positive_rate']:.2%}")
        print(f"   • Taux FN: {attack['false_negative_rate']:.2%}")
        
        print(f"\n📋 MÉTRIQUES PAR CLASSE:")
        print(f"   {'Classe':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
        print("   " + "-" * 60)
        
        for class_name, metrics in report["per_class"].items():
            print(f"   {class_name:<20} {metrics['precision']:>10.2%} "
                  f"{metrics['recall']:>10.2%} {metrics['f1_score']:>10.2%} "
                  f"{metrics['support']:>10,}")
        
        print("\n" + "=" * 70)
    
    def save_report(self, filepath: str):
        """Sauvegarde le rapport en JSON."""
        report = self.get_report()
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"✅ Rapport sauvegardé: {filepath}")
    
    def get_recent_errors(self, n: int = 10) -> List[Dict]:
        """Retourne les N dernières erreurs de prédiction."""
        errors = [p for p in self.predictions_history if not p['is_correct']]
        return errors[-n:]


# ============================================================================
# TEST STANDALONE
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEST DU METRICS TRACKER")
    print("=" * 60)
    
    # Créer un tracker
    class_names = ["Normal Traffic", "DDoS", "DoS", "Bots", "Port Scanning"]
    tracker = MetricsTracker(class_names)
    
    # Simuler des prédictions
    import random
    for i in range(100):
        true = random.choice(class_names)
        # 90% de chance de prédiction correcte
        pred = true if random.random() < 0.9 else random.choice(class_names)
        conf = random.uniform(0.7, 0.99)
        
        tracker.update(true, pred, conf)
    
    # Afficher le rapport
    tracker.print_report()
    
    print("\n✅ Test réussi!")
