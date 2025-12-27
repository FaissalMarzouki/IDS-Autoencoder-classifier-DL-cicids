"""
Metrics Tracker Module
Calcule et suit les metriques de performance en temps reel
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class MetricsReport:
    """Rapport de metriques"""
    total_flows: int
    total_attacks_detected: int
    total_normal: int
    
    # Confusion metrics
    true_positives: int   # Attaque predite comme attaque
    true_negatives: int   # Normal predit comme normal
    false_positives: int  # Normal predit comme attaque
    false_negatives: int  # Attaque predite comme normal
    
    # Metriques calculees
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    false_negative_rate: float
    
    # Par classe
    per_class_metrics: Dict[str, Dict]
    confusion_matrix: Dict[str, Dict[str, int]]
    
    # Temps
    start_time: str
    end_time: str
    duration_seconds: float
    flows_per_second: float
    
    def to_dict(self) -> Dict:
        return {
            'summary': {
                'total_flows': self.total_flows,
                'attacks_detected': self.total_attacks_detected,
                'normal_traffic': self.total_normal,
            },
            'confusion': {
                'true_positives': self.true_positives,
                'true_negatives': self.true_negatives,
                'false_positives': self.false_positives,
                'false_negatives': self.false_negatives,
            },
            'metrics': {
                'accuracy': round(self.accuracy, 4),
                'precision': round(self.precision, 4),
                'recall': round(self.recall, 4),
                'f1_score': round(self.f1_score, 4),
                'false_positive_rate': round(self.false_positive_rate, 4),
                'false_negative_rate': round(self.false_negative_rate, 4),
            },
            'per_class': self.per_class_metrics,
            'confusion_matrix': self.confusion_matrix,
            'timing': {
                'start_time': self.start_time,
                'end_time': self.end_time,
                'duration_seconds': round(self.duration_seconds, 2),
                'flows_per_second': round(self.flows_per_second, 2),
            }
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class MetricsTracker:
    """Tracker de metriques en temps reel"""
    
    def __init__(self, class_names: List[str]):
        self.class_names = class_names
        self.reset()
    
    def reset(self):
        """Reinitialise toutes les metriques"""
        self.start_time = datetime.now()
        self.total_flows = 0
        
        # Compteurs par classe: [true_label][predicted_label] = count
        self.confusion = defaultdict(lambda: defaultdict(int))
        
        # Listes pour analyse detaillee
        self.predictions = []
        self.true_labels = []
        self.confidences = []
        self.anomaly_scores = []
    
    def update(self, true_label: str, predicted_label: str, 
               confidence: float, anomaly_score: float):
        """
        Met a jour les metriques avec une nouvelle prediction
        
        Args:
            true_label: Label reel du flux
            predicted_label: Label predit par le modele
            confidence: Confiance de la prediction
            anomaly_score: Score d'anomalie
        """
        self.total_flows += 1
        self.confusion[true_label][predicted_label] += 1
        
        self.predictions.append(predicted_label)
        self.true_labels.append(true_label)
        self.confidences.append(confidence)
        self.anomaly_scores.append(anomaly_score)
    
    def get_report(self) -> MetricsReport:
        """Genere un rapport complet des metriques"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Calculer TP, TN, FP, FN (binaire: Normal vs Attack)
        tp = tn = fp = fn = 0
        total_attacks = 0
        total_normal = 0
        
        for true_label, preds in self.confusion.items():
            is_true_attack = true_label != 'Normal Traffic'
            
            for pred_label, count in preds.items():
                is_pred_attack = pred_label != 'Normal Traffic'
                
                if is_true_attack:
                    total_attacks += count
                    if is_pred_attack:
                        tp += count  # Attaque correctement detectee
                    else:
                        fn += count  # Attaque manquee
                else:
                    total_normal += count
                    if is_pred_attack:
                        fp += count  # Fausse alerte
                    else:
                        tn += count  # Normal correctement identifie
        
        # Metriques globales
        accuracy = (tp + tn) / max(self.total_flows, 1)
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-10)
        fpr = fp / max(fp + tn, 1)
        fnr = fn / max(fn + tp, 1)
        
        # Metriques par classe
        per_class = {}
        for cls in self.class_names:
            cls_tp = self.confusion[cls].get(cls, 0)
            cls_total_true = sum(self.confusion[cls].values())
            cls_total_pred = sum(self.confusion[t].get(cls, 0) for t in self.confusion)
            
            cls_precision = cls_tp / max(cls_total_pred, 1)
            cls_recall = cls_tp / max(cls_total_true, 1)
            cls_f1 = 2 * cls_precision * cls_recall / max(cls_precision + cls_recall, 1e-10)
            
            per_class[cls] = {
                'true_count': cls_total_true,
                'predicted_count': cls_total_pred,
                'correct': cls_tp,
                'precision': round(cls_precision, 4),
                'recall': round(cls_recall, 4),
                'f1_score': round(cls_f1, 4)
            }
        
        # Matrice de confusion
        confusion_matrix = {
            true_label: dict(preds) 
            for true_label, preds in self.confusion.items()
        }
        
        return MetricsReport(
            total_flows=self.total_flows,
            total_attacks_detected=tp + fp,
            total_normal=tn + fn,
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            false_positive_rate=fpr,
            false_negative_rate=fnr,
            per_class_metrics=per_class,
            confusion_matrix=confusion_matrix,
            start_time=self.start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            flows_per_second=self.total_flows / max(duration, 0.001)
        )
    
    def print_summary(self):
        """Affiche un resume des metriques"""
        report = self.get_report()
        
        print("\n" + "="*60)
        print("RAPPORT DE DETECTION IDS")
        print("="*60)
        
        print(f"\nFlux traites: {report.total_flows}")
        print(f"Duree: {report.duration_seconds:.2f}s ({report.flows_per_second:.1f} flux/s)")
        
        print("\n--- METRIQUES BINAIRES (Attack vs Normal) ---")
        print(f"Accuracy:     {report.accuracy:.2%}")
        print(f"Precision:    {report.precision:.2%}")
        print(f"Recall:       {report.recall:.2%}")
        print(f"F1-Score:     {report.f1_score:.2%}")
        
        print("\n--- ERREURS ---")
        print(f"Faux Positifs (FP): {report.false_positives} ({report.false_positive_rate:.2%})")
        print(f"Faux Negatifs (FN): {report.false_negatives} ({report.false_negative_rate:.2%})")
        
        print("\n--- MATRICE DE CONFUSION ---")
        print(f"True Positives:  {report.true_positives}")
        print(f"True Negatives:  {report.true_negatives}")
        print(f"False Positives: {report.false_positives}")
        print(f"False Negatives: {report.false_negatives}")
        
        print("\n" + "="*60)
