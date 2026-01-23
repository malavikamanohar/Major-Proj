import json
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class UserProfile(models.Model):
    """Extended user profile with role and department info"""
    ROLE_CHOICES = [
        ('DOCTOR', 'Doctor'),
        ('ADMIN', 'Administrator'),
        ('STAFF', 'Staff'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='STAFF')
    department = models.CharField(max_length=100, blank=True, null=True)
    license_number = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class LLMUsage(models.Model):
    """Track daily LLM API usage per model and API key"""
    model_name = models.CharField(max_length=100, db_index=True)
    api_key_fingerprint = models.CharField(max_length=64, db_index=True, help_text="SHA256 hash of API key (first 12 chars)")
    date = models.DateField(db_index=True, default=timezone.now)
    count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['model_name', 'api_key_fingerprint', 'date']]
        ordering = ['-date', 'model_name']

    def __str__(self):
        return f"{self.model_name} - {self.api_key_fingerprint[:8]} - {self.date}: {self.count}"


class Patient(models.Model):
    """Patient model to store demographics and basic info"""
    patient_id = models.CharField(max_length=50, unique=True, db_index=True)
    age = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(150)])
    sex = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
    chief_complaint = models.TextField()
    symptoms = models.TextField(help_text="Free-text symptoms")
    past_medical_history = models.TextField(blank=True, null=True)
    medications = models.TextField(blank=True, null=True)
    clinical_notes = models.TextField(blank=True, null=True)
    previous_visit = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='follow_ups', help_text="Link to previous visit for follow-up patients")
    is_follow_up = models.BooleanField(default=False, help_text="Mark if this is a follow-up visit")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.patient_id} - {self.chief_complaint[:50]}"

    def get_all_visits(self):
        """Get all visits in chronological order (initial + follow-ups)"""
        if self.previous_visit:
            # This is a follow-up, get the initial visit's chain
            initial = self.previous_visit
            while initial.previous_visit:
                initial = initial.previous_visit
            # Return initial visit + all its follow-ups
            visits = [initial] + list(initial.follow_ups.all().order_by('created_at'))
            return visits
        else:
            # This is an initial visit, return self + follow-ups
            return [self] + list(self.follow_ups.all().order_by('created_at'))

    def get_visit_number(self):
        """Get the visit number in the sequence"""
        all_visits = self.get_all_visits()
        return all_visits.index(self) + 1 if self in all_visits else 1


class Vitals(models.Model):
    """Vital signs for a patient"""
    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='vitals')
    blood_pressure_systolic = models.IntegerField(help_text="mmHg", null=True, blank=True)
    blood_pressure_diastolic = models.IntegerField(help_text="mmHg", null=True, blank=True)
    heart_rate = models.IntegerField(help_text="bpm", null=True, blank=True)
    respiratory_rate = models.IntegerField(help_text="breaths/min", null=True, blank=True)
    oxygen_saturation = models.FloatField(help_text="SpO2 %", validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    temperature = models.FloatField(help_text="°F", null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Vitals"

    def __str__(self):
        return f"Vitals for {self.patient.patient_id}"


class Labs(models.Model):
    """Laboratory results for a patient"""
    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='labs')
    lab_results = models.TextField(help_text="Free-text or structured lab results")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Labs"

    def __str__(self):
        return f"Labs for {self.patient.patient_id}"


class ClinicalSummary(models.Model):
    """Structured clinical summary generated from patient data"""
    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='clinical_summary')
    summary_text = models.TextField(help_text="Structured clinical summary")
    embedding = models.BinaryField(help_text="Numpy array of embedding stored as binary", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Clinical Summaries"

    def __str__(self):
        return f"Summary for {self.patient.patient_id}"


class KnowledgeCase(models.Model):
    """MIMIC-IV-like cases in the knowledge base"""
    case_id = models.CharField(max_length=50, unique=True, db_index=True)
    summary_text = models.TextField(help_text="Clinical summary of the case")
    diagnosis = models.CharField(max_length=500)
    outcome = models.TextField(blank=True, null=True)
    embedding = models.BinaryField(help_text="Numpy array of embedding stored as binary", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['case_id']

    def __str__(self):
        return f"{self.case_id} - {self.diagnosis}"


class DiagnosisResult(models.Model):
    """Diagnosis results generated by the RAG system"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='diagnosis_results')
    source_result = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reused_results')
    case_fingerprint = models.CharField(max_length=64, db_index=True, help_text="Deterministic hash of patient presentation", blank=True, null=True)
    differential_diagnoses = models.JSONField(help_text="List of diagnoses with likelihood percentages")
    triage_level = models.CharField(max_length=20, choices=[
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical')
    ])
    explanation = models.TextField(help_text="Medical reasoning and explanation")
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Model confidence score (0-1)"
    )
    retrieved_cases = models.JSONField(help_text="List of retrieved case IDs used for reasoning")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['case_fingerprint']),
        ]

    def __str__(self):
        return f"Diagnosis for {self.patient.patient_id} - {self.triage_level}"

    def get_top_diagnosis(self):
        """Get the most likely diagnosis"""
        if self.differential_diagnoses:
            return max(self.differential_diagnoses, key=lambda x: x.get('likelihood', 0))
        return None


class DiagnosisJob(models.Model):
    """Background job tracking for asynchronous diagnosis generation"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='diagnosis_jobs')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='diagnosis_jobs')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    case_fingerprint = models.CharField(max_length=64, db_index=True)
    reuse_source = models.ForeignKey('DiagnosisResult', null=True, blank=True, on_delete=models.SET_NULL, related_name='reuse_jobs')
    diagnosis = models.ForeignKey('DiagnosisResult', null=True, blank=True, on_delete=models.SET_NULL, related_name='origin_jobs')
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Job {self.id} - {self.status}"

