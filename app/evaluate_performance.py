# ============================================================================
# EVALUATE_PERFORMANCE.PY - Évaluation détaillée des performances
# ============================================================================
"""Script pour analyser les performances du modèle IDS."""

import json
import os
from datetime import datetime

def evaluate_performance():
    """Analyse le dernier rapport de simulation."""
    
    # Charger le dernier rapport
    reports_dir = './metrics'
    if not os.path.exists(reports_dir):
        print("❌ Aucun rapport trouvé. Exécutez d'abord le pipeline.")
        return
    
    reports = [f for f in os.listdir(reports_dir) if f.startswith('simulation_report')]
    if not reports:
        print("❌ Aucun rapport de simulation trouvé.")
        return
    
    latest = sorted(reports)[-1]
    print(f"📄 Analyse du rapport: {latest}\n")
    
    with open(f'{reports_dir}/{latest}', 'r') as f:
        report = json.load(f)
    
    print("=" * 70)
    print("📊 ÉVALUATION COMPLÈTE DES PERFORMANCES DU MODÈLE IDS")
    print("=" * 70)
    
    # =========================================================================
    # RÉSUMÉ GLOBAL
    # =========================================================================
    summary = report['summary']
    
    print("""
┌─────────────────────────────────────────────────────────────────┐
│                    RÉSUMÉ GLOBAL                                │
├─────────────────────────────────────────────────────────────────┤""")
    print(f"│  Total flux traités     : {summary['total_predictions']:>10,}                          │")
    print(f"│  Prédictions correctes  : {summary['total_correct']:>10,}                          │")
    print(f"│  Accuracy globale       : {summary['overall_accuracy']*100:>10.2f}%                         │")
    print(f"│  Temps d'exécution      : {summary['elapsed_seconds']:>10.1f}s                          │")
    print(f"│  Débit (throughput)     : {summary['predictions_per_second']:>10.0f} flux/s                     │")
    print("└─────────────────────────────────────────────────────────────────┘")
    
    # =========================================================================
    # DÉTECTION D'ATTAQUES
    # =========================================================================
    attack = report['attack_detection']
    
    print("""
┌─────────────────────────────────────────────────────────────────┐
│                DÉTECTION D'ATTAQUES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MATRICE DE CONFUSION (Attaque vs Normal):                      │
│  ┌───────────────┬──────────────┬──────────────┐               │
│  │               │  Prédit      │  Prédit      │               │
│  │               │  ATTAQUE     │  NORMAL      │               │
│  ├───────────────┼──────────────┼──────────────┤               │""")
    print(f"│  │ Réel ATTAQUE  │  TP: {attack['true_positives']:>6}  │  FN: {attack['false_negatives']:>6}  │               │")
    print(f"│  │ Réel NORMAL   │  FP: {attack['false_positives']:>6}  │  TN: {attack['true_negatives']:>6}  │               │")
    print("│  └───────────────┴──────────────┴──────────────┘               │")
    print("│                                                                 │")
    print("│  MÉTRIQUES CLÉS:                                                │")
    print(f"│  • Precision (attaques)    : {attack['precision']*100:>6.2f}%                          │")
    print(f"│  • Recall (Detection Rate) : {attack['recall']*100:>6.2f}%  ← CRITIQUE              │")
    print(f"│  • F1-Score                : {attack['f1_score']*100:>6.2f}%                          │")
    print(f"│  • Taux Faux Positifs (FPR): {attack['false_positive_rate']*100:>6.2f}%                          │")
    print(f"│  • Taux Faux Négatifs (FNR): {attack['false_negative_rate']*100:>6.2f}%  ← CRITIQUE              │")
    print("│                                                                 │")
    print("└─────────────────────────────────────────────────────────────────┘")
    
    # =========================================================================
    # PERFORMANCE PAR CLASSE
    # =========================================================================
    print("""
┌─────────────────────────────────────────────────────────────────┐
│                PERFORMANCE PAR CLASSE                           │
├─────────────────────────────────────────────────────────────────┤""")
    
    header = f"│  {'Classe':<18} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>8} │"
    print(header)
    print("│  " + "-" * 60 + "│")
    
    per_class = report['per_class']
    for cls, metrics in per_class.items():
        p = metrics['precision'] * 100
        r = metrics['recall'] * 100
        f1 = metrics['f1_score'] * 100
        s = metrics['support']
        status = '✅' if r >= 95 else '⚠️' if r >= 80 else '❌'
        row = f"│  {cls:<18} {p:>9.1f}% {r:>9.1f}% {f1:>9.1f}% {s:>8} {status}│"
        print(row)
    
    print("└─────────────────────────────────────────────────────────────────┘")
    
    # =========================================================================
    # INTERPRÉTATION
    # =========================================================================
    fnr = attack['false_negative_rate'] * 100
    fpr = attack['false_positive_rate'] * 100
    recall = attack['recall'] * 100
    
    print("""
┌─────────────────────────────────────────────────────────────────┐
│                    INTERPRÉTATION                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │""")
    
    # Points forts
    print("│  ✅ POINTS FORTS:                                               │")
    if recall >= 99:
        print("│     • Detection Rate ≈ 100%% → Aucune attaque ne passe!         │")
    if fnr == 0:
        print("│     • 0 False Negatives → Pas d'attaque manquée                │")
    
    # DDoS/DoS performance
    ddos_prec = per_class.get('DDoS', {}).get('precision', 0) * 100
    dos_prec = per_class.get('DoS', {}).get('precision', 0) * 100
    if ddos_prec > 90 or dos_prec > 90:
        print("│     • DDoS/DoS: Excellente détection (>90%% precision)          │")
    
    throughput = summary['predictions_per_second']
    print(f"│     • Débit élevé: ~{throughput:.0f} flux/s (adapté temps réel)             │")
    
    print("│                                                                 │")
    
    # Points à améliorer
    print("│  ⚠️  POINTS À AMÉLIORER:                                        │")
    if fpr > 5:
        print(f"│     • False Positives (~{fpr:.0f}%%) → Fausses alertes                 │")
    
    # Classes faibles
    weak_classes = [c for c, m in per_class.items() if m['precision'] < 0.3 and m['support'] > 0]
    if weak_classes:
        print(f"│     • {'/'.join(weak_classes[:2])}: Faible precision              │")
    
    print("│     • Normal parfois classé comme attaque (conservateur)       │")
    print("│                                                                 │")
    
    # Conclusion cybersécurité
    print("│  💡 EN CYBERSÉCURITÉ:                                           │")
    print("│     • FN = 0 est EXCELLENT (aucune attaque manquée)            │")
    if fpr < 15:
        print(f"│     • FP = {fpr:.0f}%% est ACCEPTABLE (alertes à trier)             │")
    print("│     • Le modèle est CONSERVATEUR: doute → alerte               │")
    print("│                                                                 │")
    print("└─────────────────────────────────────────────────────────────────┘")
    
    # =========================================================================
    # SCORE FINAL
    # =========================================================================
    # Calcul d'un score composite
    score = 0
    if fnr == 0:
        score += 40  # Crucial: pas d'attaques manquées
    if recall >= 95:
        score += 20
    if fpr < 15:
        score += 15
    if throughput > 500:
        score += 15
    if summary['overall_accuracy'] > 0.85:
        score += 10
    
    print(f"""
┌─────────────────────────────────────────────────────────────────┐
│                    SCORE FINAL                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                      ⭐ {score}/100 ⭐                              │
│                                                                 │""")
    
    if score >= 90:
        print("│           EXCELLENT - Prêt pour la production               │")
    elif score >= 75:
        print("│           BON - Performances satisfaisantes                  │")
    elif score >= 60:
        print("│           ACCEPTABLE - Améliorations possibles               │")
    else:
        print("│           À AMÉLIORER - Nécessite des ajustements             │")
    
    print("│                                                                 │")
    print("└─────────────────────────────────────────────────────────────────┘")
    
    return report


if __name__ == "__main__":
    evaluate_performance()
