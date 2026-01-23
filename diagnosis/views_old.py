from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import (
    Patient,
    Vitals,
    Labs,
    ClinicalSummary,
    KnowledgeCase,
    DiagnosisResult,
    DiagnosisJob,
    LLMUsage,
    UserProfile,
)
from .forms import PatientForm, VitalsForm, LabsForm, RegistrationForm, LoginForm, FollowUpForm
from .services import (
    ClinicalSummaryGenerator,
    RAGService,
    CaseFingerprintService,
    DiagnosisJobService,
)


def user_login(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    
    return render(request, 'diagnosis/login.html', {'form': form})


def user_register(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Account created successfully! Welcome, {user.first_name}.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RegistrationForm()
    
    return render(request, 'diagnosis/register.html', {'form': form})


def user_logout(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


def home(request):
    """Public landing page"""
    return render(request, 'diagnosis/home.html')


@login_required
def dashboard(request):
    """Main dashboard with statistics"""
    user_profile = request.user.profile
    
    # Calculate statistics
    total_patients = Patient.objects.filter(is_follow_up=False).count()
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    diagnoses_today = DiagnosisResult.objects.filter(created_at__date=today).count()
    diagnoses_this_week = DiagnosisResult.objects.filter(created_at__date__gte=week_ago).count()
    
    # Triage distribution
    triage_stats_queryset = DiagnosisResult.objects.values('triage_level').annotate(count=Count('id'))
    triage_stats = list(triage_stats_queryset)
    triage_total = sum(stat['count'] for stat in triage_stats)
    if triage_total:
        for stat in triage_stats:
            stat['percentage'] = round((stat['count'] / triage_total) * 100, 2)
    else:
        for stat in triage_stats:
            stat['percentage'] = 0
    
    # Recent patients (only initial visits)
    recent_patients = list(Patient.objects.filter(is_follow_up=False).order_by('-created_at')[:5])
    recent_diagnoses = list(DiagnosisResult.objects.select_related('patient').all()[:10])
    latest_diagnosis = recent_diagnoses[0] if recent_diagnoses else None
    
    pending_jobs_qs = DiagnosisJob.objects.filter(
        status__in=[DiagnosisJob.Status.PENDING, DiagnosisJob.Status.PROCESSING]
    ).select_related('patient')
    pending_jobs = list(pending_jobs_qs[:5])
    pending_jobs_total = pending_jobs_qs.count()
    
    # LLM usage today
    llm_usage_today = LLMUsage.objects.filter(date=today).aggregate(total=Count('id'))['total'] or 0
    
    context = {
        'user_profile': user_profile,
        'total_patients': total_patients,
        'diagnoses_today': diagnoses_today,
        'diagnoses_this_week': diagnoses_this_week,
        'triage_stats': triage_stats,
        'triage_total': triage_total,
        'recent_patients': recent_patients,
        'recent_diagnoses': recent_diagnoses,
        'latest_diagnosis': latest_diagnosis,
        'llm_usage_today': llm_usage_today,
        'pending_jobs': pending_jobs,
        'pending_jobs_total': pending_jobs_total,
    }
    return render(request, 'diagnosis/dashboard.html', context)


@login_required
def patient_input(request):
    """Patient data input form"""
    if request.method == 'POST':
        patient_form = PatientForm(request.POST)
        vitals_form = VitalsForm(request.POST)
        labs_form = LabsForm(request.POST)
        
        if patient_form.is_valid() and vitals_form.is_valid() and labs_form.is_valid():
            try:
                with transaction.atomic():
                    # Save patient
                    patient = patient_form.save()
                    
                    # Save vitals
                    vitals = vitals_form.save(commit=False)
                    vitals.patient = patient
                    vitals.save()
                    
                    # Save labs
                    labs = labs_form.save(commit=False)
                    labs.patient = patient
                    labs.save()
                    
                    messages.success(request, f'Patient {patient.patient_id} data saved successfully!')
                    return redirect('generate_diagnosis', patient_id=patient.patient_id)
                    
            except Exception as e:
                messages.error(request, f'Error saving patient data: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        patient_form = PatientForm()
        vitals_form = VitalsForm()
        labs_form = LabsForm()
    
    context = {
        'patient_form': patient_form,
        'vitals_form': vitals_form,
        'labs_form': labs_form,
    }
    return render(request, 'diagnosis/patient_input.html', context)


@login_required
def patient_follow_up(request, patient_id):
    """Create a follow-up visit for an existing patient"""
    previous_patient = get_object_or_404(Patient, patient_id=patient_id)
    
    if request.method == 'POST':
        patient_form = FollowUpForm(request.POST)
        vitals_form = VitalsForm(request.POST)
        labs_form = LabsForm(request.POST)
        
        if patient_form.is_valid() and vitals_form.is_valid() and labs_form.is_valid():
            try:
                with transaction.atomic():
                    # Auto-generate follow-up patient ID
                    all_visits = previous_patient.get_all_visits()
                    visit_number = len(all_visits) + 1
                    new_patient_id = f"{previous_patient.patient_id}-F{visit_number}"
                    
                    # Save new patient visit with copied demographics
                    patient = patient_form.save(commit=False)
                    patient.patient_id = new_patient_id
                    patient.age = previous_patient.age
                    patient.sex = previous_patient.sex
                    patient.past_medical_history = previous_patient.past_medical_history
                    patient.medications = previous_patient.medications
                    patient.previous_visit = previous_patient
                    patient.is_follow_up = True
                    patient.save()
                    
                    # Save vitals
                    vitals = vitals_form.save(commit=False)
                    vitals.patient = patient
                    vitals.save()
                    
                    # Save labs
                    labs = labs_form.save(commit=False)
                    labs.patient = patient
                    labs.save()
                    
                    messages.success(request, f'Follow-up visit {patient.patient_id} recorded successfully!')
                    return redirect('generate_diagnosis', patient_id=patient.patient_id)
                    
            except Exception as e:
                messages.error(request, f'Error saving follow-up data: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Empty form - no pre-filling of clinical data
        patient_form = FollowUpForm()
        vitals_form = VitalsForm()
        labs_form = LabsForm()
    
    context = {
        'patient_form': patient_form,
        'vitals_form': vitals_form,
        'labs_form': labs_form,
        'previous_patient': previous_patient,
        'is_follow_up': True,
    }
    return render(request, 'diagnosis/patient_input.html', context)


@login_required
def generate_diagnosis(request, patient_id):
    """Generate diagnosis using RAG system"""
    user_profile = request.user.profile
    
    patient = get_object_or_404(Patient, patient_id=patient_id)
    vitals = getattr(patient, 'vitals', None)
    labs = getattr(patient, 'labs', None)
    fingerprint = CaseFingerprintService.generate(patient, vitals, labs)

    existing_result = DiagnosisResult.objects.filter(case_fingerprint=fingerprint).order_by('-created_at').first()
    if existing_result:
        try:
            summary_text = ClinicalSummaryGenerator.generate(patient, vitals, labs)
            rag_service = RAGService()
            embedding = rag_service.generate_embedding(summary_text)
            embedding_binary = rag_service.numpy_to_binary(embedding)
            ClinicalSummary.objects.update_or_create(
                patient=patient,
                defaults={'summary_text': summary_text, 'embedding': embedding_binary}
            )

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

            DiagnosisJob.objects.create(
                patient=patient,
                created_by=request.user,
                status=DiagnosisJob.Status.COMPLETED,
                case_fingerprint=fingerprint,
                reuse_source=existing_result,
                diagnosis=cloned,
            )

            messages.info(request, 'Reused an identical prior assessment to save time and tokens.')
            return redirect('diagnosis_result', diagnosis_id=cloned.id)
        except Exception as exc:
            messages.error(request, f'Error reusing prior diagnosis: {exc}')
            return redirect('patient_detail', patient_id=patient_id)

    job = DiagnosisJob.objects.create(
        patient=patient,
        created_by=request.user,
        case_fingerprint=fingerprint,
        status=DiagnosisJob.Status.PENDING,
    )
    DiagnosisJobService.enqueue(job.id)
    messages.success(
        request,
        'Diagnosis request queued. You can navigate away or close the tab and return once processing completes.',
    )
    return redirect('diagnosis_job_detail', job_id=job.id)


@login_required
def diagnosis_result(request, diagnosis_id):
    """Display diagnosis results"""
    diagnosis = get_object_or_404(DiagnosisResult, id=diagnosis_id)
    patient = diagnosis.patient
    clinical_summary = getattr(patient, 'clinical_summary', None)
    
    # Get retrieved cases
    retrieved_cases = KnowledgeCase.objects.filter(
        case_id__in=diagnosis.retrieved_cases
    )
    
    context = {
        'diagnosis': diagnosis,
        'patient': patient,
        'clinical_summary': clinical_summary,
        'retrieved_cases': retrieved_cases,
    }
    return render(request, 'diagnosis/diagnosis_result.html', context)


@login_required
def diagnosis_job_detail(request, job_id):
    """Show background job status and provide link once completed"""
    job = get_object_or_404(
        DiagnosisJob.objects.select_related('patient', 'diagnosis', 'reuse_source'),
        id=job_id
    )

    profile = request.user.profile
    if job.created_by and job.created_by != request.user and profile.role == 'STAFF':
        messages.error(request, 'You do not have access to this job record.')
        return redirect('dashboard')

    context = {
        'job': job,
        'patient': job.patient,
    }
    return render(request, 'diagnosis/diagnosis_job.html', context)


@login_required
def patient_detail(request, patient_id):
    """View patient details and history"""
    patient = get_object_or_404(Patient, patient_id=patient_id)
    vitals = getattr(patient, 'vitals', None)
    labs = getattr(patient, 'labs', None)
    clinical_summary = getattr(patient, 'clinical_summary', None)
    
    # Get all visits in the chain
    all_visits = patient.get_all_visits()
    
    # Aggregate diagnosis history from all visits
    diagnosis_history = DiagnosisResult.objects.filter(
        patient__in=all_visits
    ).order_by('-created_at')
    
    job_history = patient.diagnosis_jobs.all()
    
    context = {
        'patient': patient,
        'vitals': vitals,
        'labs': labs,
        'clinical_summary': clinical_summary,
        'diagnosis_history': diagnosis_history,
        'job_history': job_history,
    }
    return render(request, 'diagnosis/patient_detail.html', context)


@login_required
def patient_list(request):
    """List all patients with search and filter"""
    search_query = request.GET.get('search', '')
    triage_filter = request.GET.get('triage', '')
    
    # Only show initial visits (not follow-ups)
    patients = Patient.objects.filter(is_follow_up=False)
    
    # Apply search
    if search_query:
        patients = patients.filter(
            Q(patient_id__icontains=search_query) |
            Q(chief_complaint__icontains=search_query) |
            Q(symptoms__icontains=search_query)
        )
    
    # Apply triage filter
    if triage_filter:
        patient_ids_with_triage = DiagnosisResult.objects.filter(
            triage_level=triage_filter
        ).values_list('patient_id', flat=True)
        patients = patients.filter(id__in=patient_ids_with_triage)
    
    context = {
        'patients': patients,
        'search_query': search_query,
        'triage_filter': triage_filter,
    }
    return render(request, 'diagnosis/patient_list.html', context)

