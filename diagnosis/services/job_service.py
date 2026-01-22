"""Background execution for diagnosis jobs"""
import logging
from concurrent.futures import ThreadPoolExecutor

from django.db import close_old_connections, transaction

from .case_fingerprint_service import CaseFingerprintService
from .clinical_summary_generator import ClinicalSummaryGenerator
from .llm_service import LLMService
from .rag_service import RAGService

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)


class DiagnosisJobService:
    """Dispatch and process diagnosis jobs asynchronously."""

    executor = _executor

    @classmethod
    def enqueue(cls, job_id):
        cls.executor.submit(cls._process_job, job_id)

    @classmethod
    def _process_job(cls, job_id):
        from diagnosis.models import ClinicalSummary, DiagnosisJob, DiagnosisResult, KnowledgeCase

        close_old_connections()
        try:
            job = DiagnosisJob.objects.select_related("patient").get(pk=job_id)
        except DiagnosisJob.DoesNotExist:
            logger.warning("DiagnosisJob %s disappeared before processing", job_id)
            return

        if job.status in [DiagnosisJob.Status.COMPLETED, DiagnosisJob.Status.FAILED]:
            return

        patient = job.patient
        vitals = getattr(patient, "vitals", None)
        labs = getattr(patient, "labs", None)

        fingerprint = job.case_fingerprint or CaseFingerprintService.generate(patient, vitals, labs)
        if job.case_fingerprint != fingerprint:
            job.case_fingerprint = fingerprint
            job.save(update_fields=["case_fingerprint", "updated_at"])

        try:
            summary_text = ClinicalSummaryGenerator.generate(patient, vitals, labs)
            rag_service = RAGService()
            embedding = rag_service.generate_embedding(summary_text)
            embedding_binary = rag_service.numpy_to_binary(embedding)

            # Retry logic for database locked errors
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        ClinicalSummary.objects.update_or_create(
                            patient=patient,
                            defaults={"summary_text": summary_text, "embedding": embedding_binary},
                        )
                    break
                except Exception as db_err:
                    if "database is locked" in str(db_err) and attempt < max_retries - 1:
                        import time
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    raise

            # Ensure no other result landed since enqueue (or after summary computation)
            existing_result = (
                DiagnosisResult.objects.filter(case_fingerprint=fingerprint)
                .order_by("-created_at")
                .first()
            )
            if existing_result:
                cloned = DiagnosisResult.objects.create(
                    patient=patient,
                    source_result=existing_result,
                    case_fingerprint=fingerprint,
                    differential_diagnoses=existing_result.differential_diagnoses,
                    triage_level=existing_result.triage_level,
                    explanation=existing_result.explanation,
                    confidence_score=existing_result.confidence_score,
                    retrieved_cases=existing_result.retrieved_cases,
                )
                job.reuse_source = existing_result
                job.diagnosis = cloned
                job.status = DiagnosisJob.Status.COMPLETED
                job.save(update_fields=["reuse_source", "diagnosis", "status", "updated_at"])
                return

            job.status = DiagnosisJob.Status.PROCESSING
            job.save(update_fields=["status", "updated_at"])

            rag_service.get_or_build_index()
            retrieved_case_ids = rag_service.retrieve_similar_cases(embedding, k=5)
            retrieved_cases = list(KnowledgeCase.objects.filter(case_id__in=retrieved_case_ids))

            llm_service = LLMService()
            diagnosis_payload = llm_service.generate_diagnosis(summary_text, retrieved_cases)

            diagnosis = DiagnosisResult.objects.create(
                patient=patient,
                case_fingerprint=fingerprint,
                differential_diagnoses=diagnosis_payload["differential_diagnoses"],
                triage_level=diagnosis_payload["triage_level"],
                explanation=diagnosis_payload["explanation"],
                confidence_score=diagnosis_payload["confidence_score"],
                retrieved_cases=retrieved_case_ids,
            )

            job.diagnosis = diagnosis
            job.status = DiagnosisJob.Status.COMPLETED
            job.save(update_fields=["diagnosis", "status", "updated_at"])
        except Exception as exc:
            logger.exception("Diagnosis job %s failed", job_id)
            job.status = DiagnosisJob.Status.FAILED
            job.error_message = str(exc)
            job.save(update_fields=["status", "error_message", "updated_at"])
        finally:
            close_old_connections()
