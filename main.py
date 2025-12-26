import threading
from processors.preprocessor import DataPreprocessor
from processors.detector import IDSDetector
from processors.explainer import LLMExplainer
from config import TOPICS

if __name__ == "__main__":
    # 1. Prétraitement : raw -> features
    p = DataPreprocessor(TOPICS['raw'], TOPICS['features'])
    # 2. Détection : features -> alerts
    d = IDSDetector(TOPICS['features'], TOPICS['alerts'])
    # 3. Explication : alerts -> explanations
    e = LLMExplainer(TOPICS['alerts'], TOPICS['explanations'])

    for worker in [p, d, e]:
        threading.Thread(target=worker.start, daemon=True).start()

    print("Pipeline IDS Multimodal actif...")
    while True: pass # Garder le script en vie
