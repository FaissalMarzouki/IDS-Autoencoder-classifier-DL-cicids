"""
Client LLM - Interface pour différents providers (OpenAI, Anthropic, Ollama)
"""
import json
import logging
import time
import random
from typing import Dict, Any
import sys
import os
import re
from google import genai
from google.genai import types

# Ajouter le répertoire parent au path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LLM_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLMClient:
    """Client unifié pour différents providers LLM"""
    
    def __init__(self):
        self.provider = LLM_CONFIG['provider']
        self.model = LLM_CONFIG['model']
        self.temperature = LLM_CONFIG['temperature']
        self.max_tokens = LLM_CONFIG['max_tokens']
        self.system_prompt = LLM_CONFIG['system_prompt']
        
        # Initialiser le client selon le provider
        try:
            if self.provider == 'openai':
                self._init_openai()
            elif self.provider == 'anthropic':
                self._init_anthropic()
            elif self.provider == 'ollama':
                self._init_ollama()
            elif self.provider == 'groq':
                self._init_groq()
            elif self.provider == 'openrouter':
                self._init_openrouter()
            elif self.provider == 'google':
                self._init_google()
            else:
                raise ValueError(f"Provider non supporté: {self.provider}")
            
            logger.info(f"✅ LLM Client initialisé | Provider: {self.provider} | Model: {self.model}")
        except ImportError as e:
            logger.error(f"❌ Erreur d'importation: {e}")
            raise
    
    def _init_openai(self):
        """Initialise le client OpenAI"""
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=LLM_CONFIG['openai_api_key'])
        except ImportError:
            logger.error("❌ Module 'openai' non installé. Installer avec: pip install openai")
            raise
    
    def _init_anthropic(self):
        """Initialise le client Anthropic"""
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=LLM_CONFIG['anthropic_api_key'])
        except ImportError:
            logger.error("❌ Module 'anthropic' non installé. Installer avec: pip install anthropic")
            raise
    
    def _init_ollama(self):
        """Initialise le client Ollama (local)"""
        try:
            import requests
            self.client = requests
            self.ollama_base_url = LLM_CONFIG.get('ollama_base_url', 'http://localhost:11434')
            # Vérifier que le serveur Ollama est accessible
            try:
                response = self.client.get(f'{self.ollama_base_url}/api/tags')
                if response.status_code == 200:
                    logger.info(f"✅ Serveur Ollama accessible à {self.ollama_base_url}")
                else:
                    logger.warning(f"⚠️ Serveur Ollama retourne le code {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Serveur Ollama non accessible: {e}. Le client tentera la connexion lors du premier appel.")
        except ImportError:
            logger.error("❌ Module 'requests' non installé. Installer avec: pip install requests")
            raise
    
    def _init_groq(self):
        """Initialise le client Groq"""
        try:
            from openai import OpenAI

            # Liste des clés Groq (rotation si rate limit)
            self.groq_keys = LLM_CONFIG.get('groq_api_keys') or []
            if not self.groq_keys and LLM_CONFIG.get('groq_api_key'):
                self.groq_keys = [LLM_CONFIG['groq_api_key']]

            if not self.groq_keys:
                raise ValueError("Aucune clé Groq fournie (GROQ_API_KEY ou GROQ_API_KEYS)")

            self.groq_key_index = 0
            self._set_groq_client(OpenAI, self.groq_keys[self.groq_key_index])
        except ImportError:
            logger.error("❌ Module 'openai' non installé. Installer avec: pip install openai")
            raise

    def _set_groq_client(self, OpenAI, api_key: str) -> None:
        """Initialise le client Groq avec la clé donnée."""
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        self.current_groq_key = api_key

    def _rotate_groq_key(self) -> bool:
        """Passe à la clé Groq suivante en cas de rate-limit."""
        if not hasattr(self, 'groq_keys') or len(self.groq_keys) <= 1:
            return False

        self.groq_key_index = (self.groq_key_index + 1) % len(self.groq_keys)
        try:
            from openai import OpenAI
            self._set_groq_client(OpenAI, self.groq_keys[self.groq_key_index])
            logger.warning(
                f"🔄 Changement de clé Groq (clé #{self.groq_key_index + 1}/{len(self.groq_keys)}) après rate limit"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Impossible de changer de clé Groq: {e}")
            return False
    
    def _init_openrouter(self):
        """Initialise le client OpenRouter (compatible OpenAI)"""
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=LLM_CONFIG['openrouter_api_key'],
                base_url="https://openrouter.ai/api/v1"
            )
        except ImportError:
            logger.error("❌ Module 'openai' non installé. Installer avec: pip install openai")
            raise

    def _init_google(self):
        """Initialise le client Google Generative AI"""
        try:
            # Force l'utilisation de l'API v1 (gemini-1.5-flash n'est pas disponible sur v1beta)
            self.client = genai.Client(
                api_key=LLM_CONFIG['google_api_key'],
                http_options={'api_version': 'v1'}
            )
        except Exception as e:
            logger.error(f"❌ Erreur init Google: {e}")
            raise
    
    def generate_explanation(self, prompt: str) -> Dict[str, Any]:
        """
        Génère une explication via le LLM
        
        Args:
            prompt: Prompt structuré contenant les infos de l'alerte
            
        Returns:
            Dict contenant l'explication parsée
        """
        base_backoff = 5
        consecutive_quota_errors = 0

        while True:
            try:
                if self.provider == 'openai':
                    response_text = self._call_openai(prompt)
                elif self.provider == 'anthropic':
                    response_text = self._call_anthropic(prompt)
                elif self.provider == 'ollama':
                    response_text = self._call_ollama(prompt)
                elif self.provider == 'groq':
                    response_text = self._call_groq(prompt)
                elif self.provider == 'openrouter':
                    response_text = self._call_openrouter(prompt)
                elif self.provider == 'google':
                    response_text = self._call_google(prompt)
                else:
                    raise ValueError(f"Provider non supporté: {self.provider}")

                # Parser la réponse et sortir de la boucle si succès
                explanation = self._parse_explanation(response_text)
                return explanation

            except Exception as e:
                error_text = str(e).lower()
                if any(token in error_text for token in ['429', 'rate limit', 'too many requests']):
                    # Rotation de clé Groq si disponible
                    if self.provider == 'groq' and self._rotate_groq_key():
                        consecutive_quota_errors = 0
                        continue

                    consecutive_quota_errors += 1
                    backoff_seconds = base_backoff * (2 ** (consecutive_quota_errors - 1))
                    logger.warning(f"⚠️ Quota dépassé ({consecutive_quota_errors} consécutif), nouvel essai dans {backoff_seconds}s : {e}")
                    time.sleep(backoff_seconds + random.uniform(0, 1))
                    continue

                logger.error(f"❌ Erreur critique génération explication: {e}")
                return self._fallback_explanation()
    
    def _call_openai(self, prompt: str) -> str:
        """Appelle l'API OpenAI"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        return response.choices[0].message.content
    
    def _call_anthropic(self, prompt: str) -> str:
        """Appelle l'API Anthropic"""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
    
    def _call_ollama(self, prompt: str) -> str:
        """Appelle l'API Ollama (local)"""
        try:
            response = self.client.post(
                f'{self.ollama_base_url}/api/generate',
                json={
                    'model': self.model,
                    'prompt': f"{self.system_prompt}\n\n{prompt}",
                    'stream': False
                },
                timeout=1800  # Timeout 30 minutes pour les réponses longues (llama3 est lent)
            )
            response.raise_for_status()
            result = response.json()
            if 'response' in result:
                return result['response']
            else:
                logger.warning("⚠️ Réponse Ollama sans champ 'response'")
                return str(result)
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'appel Ollama: {e}")
            raise
    
    def _call_groq(self, prompt: str) -> str:
        """Appelle l'API Groq (compatible OpenAI)"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        return response.choices[0].message.content
    
    def _call_openrouter(self, prompt: str) -> str:
        """Appelle l'API OpenRouter (compatible OpenAI)"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        return response.choices[0].message.content

    def _call_google(self, prompt: str) -> str:
        """Appelle l'API Google Generative AI"""
        full_prompt = f"{self.system_prompt}\n\n{prompt}"
        
        # Configuration de la génération
        config = types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens
        )
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=config
        )
        return response.text
    
    def _parse_explanation(self, response_text: str) -> Dict[str, Any]:
        """
        Parse la réponse du LLM pour extraire les sections structurées
        Utilise des délimiteurs clairs (### Synthèse, ### Analyse, etc.)
        
        Args:
            response_text: Réponse brute du LLM
            
        Returns:
            Dict avec summary, analysis, impact, recommendations, priority
        """
        try:
            # Diviser le texte par les en-têtes (### ou **)
            text = response_text.strip()
            
            # Extraire chaque section de manière robuste (headers flexibles)
            summary = self._extract_section_robust(
                text,
                r'(?:###\s*)?(?:\*\*)?[^A-Za-z0-9]*(?:Synthèse|Résumé|Summary|Overview)',
                r'(?:###|(?:\*\*)?(?:Analyse|Analysis|Impact|Recommandations|Recommendations|Priorité|Priority))',
                "Synthèse non disponible"
            )
            analysis = self._extract_section_robust(
                text,
                r'(?:###\s*)?(?:\*\*)?[^A-Za-z0-9]*(?:Analyse|Analysis)',
                r'(?:###|(?:\*\*)?(?:Impact|Recommandations|Recommendations|Priorité|Priority|Synthèse|Résumé|Summary|Overview))',
                "Analyse non disponible"
            )
            impact = self._extract_section_robust(
                text,
                r'(?:###\s*)?(?:\*\*)?[^A-Za-z0-9]*Impact',
                r'(?:###|(?:\*\*)?(?:Recommandations|Recommendations|Priorité|Priority))',
                "Impact non disponible"
            )
            
            # Extraire les recommandations (avec puces) en ne prenant que la section dédiée
            recommendations = self._extract_recommendations(text)
            
            # Extraire la priorité (P1-P4)
            priority_match = re.search(r'\b(P[1-4])\b', text, re.IGNORECASE)
            priority = priority_match.group(1).upper() if priority_match else "P3"

            # Fallback si la synthèse n'est pas trouvée: prendre le premier paragraphe avant Analyse
            if summary.startswith("Synthèse non disponible"):
                parts = re.split(r'(?:###\s*)?(?:\*\*)?(?:Analyse|Analysis)', text, flags=re.IGNORECASE, maxsplit=1)
                candidate = parts[0] if parts else text
                candidate = re.sub(r'(?:###\s*)?(?:\*\*)?[^A-Za-z0-9]*(?:Synthèse|Résumé|Summary|Overview)[:\s-]*', '', candidate, flags=re.IGNORECASE)
                paragraphs = [p.strip() for p in re.split(r'\n\s*\n', candidate) if p.strip()]
                if paragraphs:
                    summary = paragraphs[0]
                elif analysis and not analysis.startswith("Analyse non disponible"):
                    summary = analysis.split('.')[0][:400]

            # Synthèse trop courte/incomplète: concaténer 1-2 phrases de l'analyse
            if summary and (len(summary) < 150 or not re.search(r'[.!?]$', summary)):
                sentences = re.split(r'(?<=[.!?])\s+', analysis)
                additions = []
                for s in sentences:
                    if s.strip():
                        additions.append(s.strip())
                    if len(' '.join(additions)) > 180 or len(additions) >= 2:
                        break
                if additions:
                    summary = (summary + ' ' + ' '.join(additions)).strip()[:400]
                if not re.search(r'[.!?]$', summary):
                    summary = (summary + '.').strip()
            
            return {
                "summary": summary.strip()[:400],
                "analysis": analysis.strip()[:1200],
                "impact": impact.strip()[:800],
                "recommendations": [r.strip() for r in recommendations if r.strip()][:5],
                "priority": priority
            }
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur parsing: {e}. Retour texte brut.")
            return {
                "summary": response_text[:200],
                "analysis": response_text[:500],
                "impact": "À évaluer manuellement",
                "recommendations": ["Analyser manuellement"],
                "priority": "P3"
            }
    
    def _extract_section_robust(self, text: str, start_pattern: str, end_pattern: str, default: str) -> str:
        """Extrait une section entre deux patterns"""
        try:
            start_match = re.search(start_pattern, text, re.IGNORECASE)
            if not start_match:
                return default
            
            start_pos = start_match.end()
            end_match = re.search(end_pattern, text[start_pos:], re.IGNORECASE)
            end_pos = start_pos + end_match.start() if end_match else len(text)
            
            section = text[start_pos:end_pos].strip()
            # Nettoyer les markdowns, newlines, et caractères résiduels
            section = re.sub(r'\n+\s*', ' ', section)  # Remplacer newlines par espace
            section = re.sub(r'^\*\*.*?\*\*[\s:]*', '', section)  # Enlever **Titre**
            section = re.sub(r'^[Tt]echnique\s*', '', section)  # Enlever "Technique" au début
            section = re.sub(r'^(?:de\s+flux\s+réseau[\s,:-]*)', '', section, flags=re.IGNORECASE)  # Nettoyer préfixes cassés
            section = re.sub(r'^[:\-\s]+', '', section)  # Enlever : - ou espaces au début
            section = re.sub(r'[#]+\s*$', '', section)  # Enlever les ### résiduels en fin de section
            section = re.sub(r'\s+', ' ', section)  # Normaliser espaces
            return section.strip() if section else default
        except:
            return default
    
    def _extract_recommendations(self, text: str) -> list:
        """Extrait les recommandations (lignes avec puces) uniquement dans la section Recommandations"""
        # Isoler la section Recommandations/Recommendations/Actions
        start_pattern = r'(?:###\s*)?(?:\*\*)?[^A-Za-z0-9]*(?:Recommandations|Recommendations|Actions?)'
        end_pattern = r'(?:###|(?:\*\*)?(?:Priorité|Priority|Synthèse|Résumé|Summary|Overview|Analyse|Analysis|Impact))'
        section = ""
        start_match = re.search(start_pattern, text, re.IGNORECASE)
        if start_match:
            start_pos = start_match.end()
            end_match = re.search(end_pattern, text[start_pos:], re.IGNORECASE)
            end_pos = start_pos + end_match.start() if end_match else len(text)
            section = text[start_pos:end_pos]

        recommendations = []
        if section:
            for line in section.split('\n'):
                line = line.strip()
                if line.startswith(('-', '•', '*')) or re.match(r'^\d+\.\s', line):
                    cleaned = re.sub(r'^[-•*]\s*|\d+\.\s*', '', line)
                    cleaned = re.sub(r'^\*\*|\*\*$', '', cleaned)  # Enlever les **
                    if cleaned:
                        recommendations.append(cleaned)

        # Fallback: si aucune reco capturée, chercher des puces uniquement après le header Recommandations
        if not recommendations and start_match:
            tail = text[start_match.end():]
            for line in tail.split('\n'):
                line = line.strip()
                if line.startswith(('-', '•', '*')) or re.match(r'^\d+\.\s', line):
                    cleaned = re.sub(r'^[-•*]\s*|\d+\.\s*', '', line)
                    cleaned = re.sub(r'^\*\*|\*\*$', '', cleaned)
                    if cleaned:
                        recommendations.append(cleaned)

        # Si toujours rien, retourner quelques actions génériques
        if not recommendations:
            return [
                "Analyser les journaux et bloquer les IP sources",
                "Mettre à jour les règles de pare-feu et IDS",
                "Surveiller le trafic pour détection précoce"
            ]

        return recommendations[:5]  # Max 5

    
    def _fallback_explanation(self) -> Dict[str, Any]:
        """Retourne une explication par défaut en cas d'erreur"""
        return {
            "summary": "Erreur lors de la génération de l'explication LLM",
            "analysis": "Le service LLM n'a pas pu traiter cette alerte",
            "impact": "À évaluer manuellement",
            "recommendations": [
                "Vérifier les logs du service LLM",
                "Analyser manuellement l'alerte",
                "Contacter l'équipe technique"
            ],
            "priority": "P3"
        }


if __name__ == "__main__":
    # Test du client LLM
    client = LLMClient()
    
    test_prompt = """
## 🔍 Rapport d'Analyse de Flux Réseau

### Identification
- **Flow ID**: test_001
- **Timestamp**: 2025-12-27T15:00:00Z

### Verdict
- **Classification**: DDoS
- **Confiance**: 93.00%
- **Sévérité**: 🔴 CRITIQUE
- **Est une attaque**: OUI ⚠️

### Scores d'Anomalie
- **Anomaly Score**: 0.8200
- **Reconstruction Error**: 0.024000
- **Comportement anormal détecté**: OUI

---

**Instructions pour l'analyse LLM:**
1. Analyser la classification et la confiance
2. Évaluer le score d'anomalie par rapport au seuil
3. Identifier les features qui ont contribué à cette classification
4. Recommander des actions pour l'équipe SOC
5. Attribuer un niveau de priorité (P1/P2/P3/P4)
"""
    
    print("🤖 Test du LLM Client...\n")
    explanation = client.generate_explanation(test_prompt)
    print(json.dumps(explanation, indent=2, ensure_ascii=False))
