"""Utilities for deterministic fingerprinting of patient presentations"""
import hashlib
import json
from typing import Any, Dict, Optional


class CaseFingerprintService:
    """Build a normalized fingerprint for a patient presentation."""

    @staticmethod
    def _normalize_text(value: Optional[str]) -> str:
        if not value:
            return ""
        return " ".join(value.strip().lower().split())

    @staticmethod
    def _bucket(value: Optional[float], step: int = 5) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(round(float(value) / step) * step)
        except (TypeError, ValueError):
            return None

    @classmethod
    def build_payload(cls, patient, vitals=None, labs=None) -> Dict[str, Any]:
        vitals_payload = {}
        if vitals:
            vitals_payload = {
                "bp_sys": cls._bucket(vitals.blood_pressure_systolic),
                "bp_dia": cls._bucket(vitals.blood_pressure_diastolic),
                "heart_rate": cls._bucket(vitals.heart_rate),
                "resp_rate": cls._bucket(vitals.respiratory_rate),
                # tighter tolerance for oxygen saturation and temperature
                "spo2": cls._bucket(vitals.oxygen_saturation, step=1),
                "temperature": cls._bucket(vitals.temperature, step=1),
            }

        labs_payload = cls._normalize_text(labs.lab_results) if labs and labs.lab_results else ""

        payload = {
            "age_bucket": cls._bucket(patient.age),
            "sex": patient.sex,
            "chief_complaint": cls._normalize_text(patient.chief_complaint),
            "symptoms": cls._normalize_text(patient.symptoms),
            "history": cls._normalize_text(patient.past_medical_history),
            "medications": cls._normalize_text(patient.medications),
            "notes": cls._normalize_text(patient.clinical_notes),
            "vitals": vitals_payload,
            "labs": labs_payload,
        }
        return payload

    @classmethod
    def generate(cls, patient, vitals=None, labs=None) -> str:
        payload = cls.build_payload(patient, vitals, labs)
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
