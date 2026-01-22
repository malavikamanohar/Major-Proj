"""
LLM Service - Interface with Groq API for diagnosis generation
Multi-API-key support with model cascade and quota tracking
"""
import os
import json
import time
import hashlib
import logging
from typing import List, Dict, Optional
from groq import Groq
from django.conf import settings
from django.utils import timezone
from django.db.models import F

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with Groq LLM with multi-API-key fallback"""
    
    def __init__(self):
        """Initialize Groq clients with multiple API keys"""
        configured_keys: List[str] = getattr(settings, 'GROQ_API_KEYS', [])
        if not configured_keys:
            raise ValueError("No Groq API keys configured. Set GROQ_API_KEYS or GROQ_API_KEY env vars.")

        self.api_keys = configured_keys
        self.clients = {key: Groq(api_key=key) for key in self.api_keys}
        self.api_key_fingerprints = {
            key: self._fingerprint_api_key(key) for key in self.api_keys
        }
        # Model cascade order (try models in sequence)
        self.model_cascade = [
            "llama-3.3-70b-versatile",
            "qwen/qwen3-32b",
            "llama-3.1-8b-instant",
        ]
        self.model_limits = {
            "llama-3.3-70b-versatile": 1000,
            "qwen/qwen3-32b": 1000,
            "llama-3.1-8b-instant": 14400,
        }
        self.max_retries = getattr(settings, 'LLM_MAX_RETRIES', 3)
        self.timeout = getattr(settings, 'LLM_TIMEOUT', 60)
    
    def _fingerprint_api_key(self, api_key: str) -> str:
        """Create a fingerprint of the API key for tracking"""
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:12]

    def _is_quota_error(self, error: Exception) -> bool:
        """Check if error is quota-related"""
        message = str(error).upper()
        return any(keyword in message for keyword in ["RESOURCE_EXHAUSTED", "QUOTA", "429", "RATE_LIMIT"])

    def _claim_usage_slot(self, model_name: str, api_key: str) -> bool:
        """
        Attempt to claim a usage slot for the given model and API key.
        Returns True if slot claimed successfully, False if quota reached.
        """
        from diagnosis.models import LLMUsage
        
        limit = self.model_limits.get(model_name)
        if not limit:
            return True

        fingerprint = self.api_key_fingerprints[api_key]
        usage, _ = LLMUsage.objects.get_or_create(
            model_name=model_name,
            api_key_fingerprint=fingerprint,
            date=timezone.now().date(),
            defaults={'count': 0},
        )

        updated = LLMUsage.objects.filter(
            pk=usage.pk,
            count__lt=limit,
        ).update(count=F('count') + 1, updated_at=timezone.now())

        return bool(updated)

    def _call_llm_with_retry(
        self,
        prompt: str,
        temperature: float = 0.7,
    ) -> str:
        """
        Call LLM with cascading models and API keys, reacting to quota limits.
        Tries all API keys for each model before moving to next model.
        """
        last_error: Optional[Exception] = None

        for model_index, model_name in enumerate(self.model_cascade):
            for key_index, api_key in enumerate(self.api_keys):
                client = self.clients[api_key]
                attempt = 0
                while attempt < self.max_retries:
                    if not self._claim_usage_slot(model_name, api_key):
                        last_error = Exception(
                            f"Daily quota reached for {model_name} using API key #{key_index + 1}"
                        )
                        logger.info(
                            "Daily quota reached for model %s (API key #%s). Skipping until reset.",
                            model_name,
                            key_index + 1,
                        )
                        break

                    try:
                        response = client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {"role": "user", "content": prompt}
                            ],
                            temperature=temperature,
                            max_tokens=4096,
                        )
                        if key_index > 0 or model_index > 0:
                            logger.info(
                                "LLM request succeeded using model %s (API key #%s)",
                                model_name,
                                key_index + 1,
                            )
                        return response.choices[0].message.content
                    except Exception as exc:
                        last_error = exc
                        quota_error = self._is_quota_error(exc)
                        attempt += 1

                        if not quota_error:
                            if attempt < self.max_retries:
                                wait_time = 2 ** (attempt - 1)
                                logger.warning(
                                    "LLM call failed (attempt %s/%s). Retrying in %ss...",
                                    attempt,
                                    self.max_retries,
                                    wait_time,
                                )
                                time.sleep(wait_time)
                                continue
                            raise Exception(
                                f"LLM call failed after {self.max_retries} attempts using {model_name} "
                                f"(API key #{key_index + 1}): {str(exc)}"
                            )

                        logger.warning(
                            "LLM quota exhausted for model %s (API key #%s). Moving to next API key if available.",
                            model_name,
                            key_index + 1,
                        )
                        break  # move to next API key for same model

            if model_index < len(self.model_cascade) - 1:
                logger.info(
                    "All API keys quota-limited for model %s. Trying next model...",
                    model_name,
                )

        raise Exception(
            "LLM call failed after exhausting all configured models and API keys: "
            f"{str(last_error) if last_error else 'unknown error'}"
        )
    
    def format_prompt(self, clinical_summary, retrieved_cases):
        """
        Format the prompt for the LLM with retrieved evidence
        
        Args:
            clinical_summary (str): Clinical summary of the patient
            retrieved_cases (list): List of KnowledgeCase objects
            
        Returns:
            str: Formatted prompt
        """
        prompt = """You are an emergency clinical decision support assistant. Your role is to provide differential diagnosis suggestions based on evidence from similar historical cases.

CRITICAL SAFETY REQUIREMENTS:
- You must NEVER provide a single definitive diagnosis
- Always provide differential diagnoses (multiple possibilities)
- Always express uncertainty and acknowledge limitations
- Reference retrieved cases explicitly in your reasoning
- This is decision support only - NOT a replacement for clinical judgment

PATIENT CLINICAL SUMMARY:
{clinical_summary}

RETRIEVED SIMILAR CASES FROM KNOWLEDGE BASE:
{retrieved_cases_text}

REQUIRED OUTPUT FORMAT (JSON):
{{
  "differential_diagnoses": [
    {{
      "diagnosis": "condition name",
      "likelihood": percentage (0-100),
      "reasoning": "brief explanation referencing similar cases"
    }}
  ],
  "triage_level": "LOW | MEDIUM | HIGH | CRITICAL",
  "explanation": "Comprehensive medical reasoning explaining the differential diagnoses, triage level, and explicit references to the retrieved cases that support your conclusions",
  "confidence_score": decimal (0.0-1.0),
  "disclaimer": "This is clinical decision support only. Final diagnosis and treatment decisions must be made by qualified healthcare professionals based on complete clinical assessment."
}}

INSTRUCTIONS:
1. Analyze the patient summary and retrieved cases
2. Generate 3-5 differential diagnoses ranked by likelihood
3. Assign appropriate triage level based on severity and urgency
4. Provide detailed explanation referencing the retrieved cases
5. Include confidence score reflecting certainty of the assessment
6. Output ONLY valid JSON matching the format above
"""
        
        # Format retrieved cases
        retrieved_cases_text = ""
        for idx, case in enumerate(retrieved_cases, 1):
            retrieved_cases_text += f"\nCASE {idx} (ID: {case.case_id}):\n"
            retrieved_cases_text += f"Summary: {case.summary_text}\n"
            retrieved_cases_text += f"Diagnosis: {case.diagnosis}\n"
            if case.outcome:
                retrieved_cases_text += f"Outcome: {case.outcome}\n"
            retrieved_cases_text += "\n"
        
        if not retrieved_cases_text:
            retrieved_cases_text = "No similar cases found in the knowledge base."
        
        formatted_prompt = prompt.format(
            clinical_summary=clinical_summary,
            retrieved_cases_text=retrieved_cases_text
        )
        
        return formatted_prompt
    
    def generate_diagnosis(self, clinical_summary, retrieved_cases):
        """
        Generate diagnosis using Gemini LLM with multi-API-key fallback
        
        Args:
            clinical_summary (str): Clinical summary of the patient
            retrieved_cases (list): List of KnowledgeCase objects
            
        Returns:
            dict: Parsed diagnosis result
        """
        prompt = self.format_prompt(clinical_summary, retrieved_cases)
        
        try:
            response_text = self._call_llm_with_retry(prompt)
            
            # Try to find JSON in the response
            # Sometimes the model wraps JSON in markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Validate required fields
            required_fields = ['differential_diagnoses', 'triage_level', 'explanation', 'confidence_score']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            
            # Ensure triage level is valid
            valid_triage = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
            if result['triage_level'] not in valid_triage:
                result['triage_level'] = 'MEDIUM'  # Default to medium if invalid
            
            # Ensure confidence score is between 0 and 1
            confidence = float(result['confidence_score'])
            if confidence < 0 or confidence > 1:
                result['confidence_score'] = 0.5  # Default to 0.5 if out of range
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Response text: {response_text}")
            # Return a fallback result
            return {
                'differential_diagnoses': [
                    {
                        'diagnosis': 'Unable to generate diagnosis',
                        'likelihood': 0,
                        'reasoning': 'LLM response could not be parsed'
                    }
                ],
                'triage_level': 'MEDIUM',
                'explanation': f'Error parsing LLM response: {str(e)}',
                'confidence_score': 0.0,
                'disclaimer': 'This is clinical decision support only. Final diagnosis and treatment decisions must be made by qualified healthcare professionals.'
            }
        except Exception as e:
            print(f"Error generating diagnosis: {e}")
            return {
                'differential_diagnoses': [
                    {
                        'diagnosis': 'Error generating diagnosis',
                        'likelihood': 0,
                        'reasoning': str(e)
                    }
                ],
                'triage_level': 'MEDIUM',
                'explanation': f'Error: {str(e)}',
                'confidence_score': 0.0,
                'disclaimer': 'This is clinical decision support only. Final diagnosis and treatment decisions must be made by qualified healthcare professionals.'
            }
