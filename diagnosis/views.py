from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Max
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import (
    Patient,
    Visit,
    Vitals,
    Labs,
    ClinicalSummary,
    KnowledgeCase,
    DiagnosisResult,
    DiagnosisJob,
    LLMUsage,
    UserProfile,
)
from .forms import PatientForm, VisitForm, VitalsForm, LabsForm, RegistrationForm, LoginForm
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
    total_patients = Patient.objects.count()
    total_visits = Visit.objects.count()
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
    
    # Recent patients
    recent_patients = list(Patient.objects.prefetch_related('visits').order_by('-created_at')[:5])
    
    # Recent diagnoses
    recent_diagnoses = list(DiagnosisResult.objects.select_related('visit__patient').order_by('-created_at')[:10])
    latest_diagnosis = recent_diagnoses[0] if recent_diagnoses else None
    
    # Pending jobs
    pending_jobs_qs = DiagnosisJob.objects.filter(
        status__in=[DiagnosisJob.Status.PENDING, DiagnosisJob.Status.PROCESSING]
    ).select_related('visit__patient')
    pending_jobs = list(pending_jobs_qs[:5])
    pending_jobs_total = pending_jobs_qs.count()
    
    # Total diagnoses count
    total_diagnoses = DiagnosisResult.objects.count()
    
    context = {
        'user_profile': user_profile,
        'total_patients': total_patients,
        'total_visits': total_visits,
        'diagnoses_today': diagnoses_today,
        'diagnoses_this_week': diagnoses_this_week,
        'triage_stats': triage_stats,
        'triage_total': triage_total,
        'recent_patients': recent_patients,
        'recent_diagnoses': recent_diagnoses,
        'latest_diagnosis': latest_diagnosis,
        'total_diagnoses': total_diagnoses,
        'pending_jobs': pending_jobs,
        'pending_jobs_total': pending_jobs_total,
    }
    return render(request, 'diagnosis/dashboard.html', context)


@login_required
def patient_input(request):
    """New patient + first visit input form"""
    if request.method == 'POST':
        patient_form = PatientForm(request.POST)
        visit_form = VisitForm(request.POST)
        vitals_form = VitalsForm(request.POST)
        labs_form = LabsForm(request.POST)
        
        if patient_form.is_valid() and visit_form.is_valid() and vitals_form.is_valid() and labs_form.is_valid():
            try:
                with transaction.atomic():
                    # Save patient
                    patient = patient_form.save()
                    
                    # Save first visit
                    visit = visit_form.save(commit=False)
                    visit.patient = patient
                    visit.visit_number = 1
                    visit.visit_type = 'INITIAL'
                    visit.save()
                    
                    # Save vitals
                    vitals = vitals_form.save(commit=False)
                    vitals.visit = visit
                    vitals.save()
                    
                    # Save labs
                    labs = labs_form.save(commit=False)
                    labs.visit = visit
                    labs.save()
                    
                    messages.success(request, f'Patient {patient.patient_id} and initial visit saved successfully!')
                    return redirect('generate_diagnosis', patient_id=patient.patient_id, visit_number=1)
                    
            except Exception as e:
                messages.error(request, f'Error saving patient data: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        patient_form = PatientForm()
        visit_form = VisitForm()
        vitals_form = VitalsForm()
        labs_form = LabsForm()
    
    context = {
        'patient_form': patient_form,
        'visit_form': visit_form,
        'vitals_form': vitals_form,
        'labs_form': labs_form,
        'is_new_patient': True,
    }
    return render(request, 'diagnosis/patient_input.html', context)


@login_required
def patient_follow_up(request, patient_id):
    """Create a follow-up visit for an existing patient"""
    patient = get_object_or_404(Patient, patient_id=patient_id)
    
    # Calculate next visit number
    next_visit_number = patient.visits.count() + 1
    
    if request.method == 'POST':
        visit_form = VisitForm(request.POST)
        vitals_form = VitalsForm(request.POST)
        labs_form = LabsForm(request.POST)
        
        if visit_form.is_valid() and vitals_form.is_valid() and labs_form.is_valid():
            try:
                with transaction.atomic():
                    # Save new visit
                    visit = visit_form.save(commit=False)
                    visit.patient = patient
                    visit.visit_number = next_visit_number
                    visit.visit_type = 'FOLLOW_UP'
                    visit.save()
                    
                    # Save vitals
                    vitals = vitals_form.save(commit=False)
                    vitals.visit = visit
                    vitals.save()
                    
                    # Save labs
                    labs = labs_form.save(commit=False)
                    labs.visit = visit
                    labs.save()
                    
                    messages.success(request, f'Follow-up visit #{visit.visit_number} recorded successfully!')
                    return redirect('generate_diagnosis', patient_id=patient.patient_id, visit_number=visit.visit_number)
                    
            except Exception as e:
                messages.error(request, f'Error saving follow-up data: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        visit_form = VisitForm()
        vitals_form = VitalsForm()
        labs_form = LabsForm()
    
    context = {
        'visit_form': visit_form,
        'vitals_form': vitals_form,
        'labs_form': labs_form,
        'patient': patient,
        'next_visit_number': next_visit_number,
        'is_follow_up': True,
    }
    return render(request, 'diagnosis/patient_input.html', context)


@login_required
def generate_diagnosis(request, patient_id, visit_number):
    """Generate diagnosis using RAG system for a specific visit"""
    user_profile = request.user.profile
    
    patient = get_object_or_404(Patient, patient_id=patient_id)
    visit = get_object_or_404(Visit, patient=patient, visit_number=visit_number)
    vitals = getattr(visit, 'vitals', None)
    labs = getattr(visit, 'labs', None)
    
    fingerprint = CaseFingerprintService.generate(visit, vitals, labs)

    # Check for existing identical diagnosis (skip if force_regenerate parameter is set)
    force_regenerate = request.GET.get('force_regenerate', 'false').lower() == 'true'
    
    # If regenerating, delete all previous diagnosis results for this visit
    if force_regenerate:
        old_diagnoses = DiagnosisResult.objects.filter(visit=visit)
        old_count = old_diagnoses.count()
        if old_count > 0:
            old_diagnoses.delete()
            messages.info(request, f'Regenerating - deleted {old_count} previous diagnosis result(s) for this visit.')
    
    existing_result = DiagnosisResult.objects.filter(case_fingerprint=fingerprint).order_by('-created_at').first()
    
    if existing_result and not force_regenerate:
        try:
            summary_text = ClinicalSummaryGenerator.generate(visit, vitals, labs)
            rag_service = RAGService()
            embedding = rag_service.generate_embedding(summary_text)
            embedding_binary = rag_service.numpy_to_binary(embedding)
            ClinicalSummary.objects.update_or_create(
                visit=visit,
                defaults={'summary_text': summary_text, 'embedding': embedding_binary}
            )

            cloned = DiagnosisResult.objects.create(
                visit=visit,
                source_result=existing_result,
                case_fingerprint=fingerprint,
                differential_diagnoses=existing_result.differential_diagnoses,
                triage_level=existing_result.triage_level,
                explanation=existing_result.explanation,
                confidence_score=existing_result.confidence_score,
                retrieved_cases=existing_result.retrieved_cases,
            )

            DiagnosisJob.objects.create(
                visit=visit,
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

    # Create new diagnosis job
    job = DiagnosisJob.objects.create(
        visit=visit,
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
def regenerate_diagnosis(request, patient_id, visit_number):
    """Regenerate diagnosis for an existing visit, bypassing cache"""
    patient = get_object_or_404(Patient, patient_id=patient_id)
    visit = get_object_or_404(Visit, patient=patient, visit_number=visit_number)
    
    messages.info(request, 'Regenerating diagnosis - bypassing cache and running fresh RAG analysis...')
    # Redirect to generate_diagnosis with force_regenerate flag
    return redirect(f"{reverse('generate_diagnosis', kwargs={'patient_id': patient_id, 'visit_number': visit_number})}?force_regenerate=true")


@login_required
def diagnosis_result(request, diagnosis_id):
    """Display diagnosis results"""
    diagnosis = get_object_or_404(DiagnosisResult.objects.select_related('visit__patient'), id=diagnosis_id)
    visit = diagnosis.visit
    patient = visit.patient
    clinical_summary = getattr(visit, 'clinical_summary', None)
    
    # Get retrieved cases
    retrieved_cases = KnowledgeCase.objects.filter(
        case_id__in=diagnosis.retrieved_cases
    )
    
    context = {
        'diagnosis': diagnosis,
        'visit': visit,
        'patient': patient,
        'clinical_summary': clinical_summary,
        'retrieved_cases': retrieved_cases,
    }
    return render(request, 'diagnosis/diagnosis_result.html', context)


@login_required
def diagnosis_job_detail(request, job_id):
    """Show background job status and provide link once completed"""
    job = get_object_or_404(
        DiagnosisJob.objects.select_related('visit__patient', 'diagnosis', 'reuse_source'),
        id=job_id
    )

    profile = request.user.profile
    if job.created_by and job.created_by != request.user and profile.role == 'STAFF':
        messages.error(request, 'You do not have access to this job record.')
        return redirect('dashboard')

    context = {
        'job': job,
        'visit': job.visit,
        'patient': job.visit.patient,
    }
    return render(request, 'diagnosis/diagnosis_job.html', context)


@login_required
def patient_detail(request, patient_id):
    """View patient details and all visits"""
    patient = get_object_or_404(Patient, patient_id=patient_id, is_deleted=False)
    
    # Get all visits for this patient
    visits = patient.visits.all().order_by('visit_number')
    
    # Get the latest visit or the one we're currently viewing
    latest_visit = visits.last() if visits.exists() else None
    
    # Get vitals/labs for latest visit
    vitals = getattr(latest_visit, 'vitals', None) if latest_visit else None
    labs = getattr(latest_visit, 'labs', None) if latest_visit else None
    clinical_summary = getattr(latest_visit, 'clinical_summary', None) if latest_visit else None
    
    # Aggregate diagnosis history from all visits
    diagnosis_history = DiagnosisResult.objects.filter(
        visit__patient=patient
    ).select_related('visit').order_by('-created_at')
    
    context = {
        'patient': patient,
        'visits': visits,
        'latest_visit': latest_visit,
        'vitals': vitals,
        'labs': labs,
        'clinical_summary': clinical_summary,
        'diagnosis_history': diagnosis_history,
    }
    return render(request, 'diagnosis/patient_detail.html', context)


@login_required
def patient_list(request):
    """List all patients with search and filter"""
    search_query = request.GET.get('search', '')
    triage_filter = request.GET.get('triage', '')
    
    # Get all active (non-deleted) patients with visit count annotation
    patients = Patient.objects.filter(is_deleted=False).annotate(
        visit_count=Count('visits'),
        latest_visit_date=Max('visits__created_at')
    ).order_by('-created_at')
    
    # Apply search
    if search_query:
        patients = patients.filter(
            Q(patient_id__icontains=search_query) |
            Q(visits__chief_complaint__icontains=search_query) |
            Q(visits__symptoms__icontains=search_query)
        ).distinct()
    
    # Apply triage filter
    if triage_filter:
        patient_ids_with_triage = DiagnosisResult.objects.filter(
            triage_level=triage_filter
        ).values_list('visit__patient_id', flat=True)
        patients = patients.filter(id__in=patient_ids_with_triage)
    
    context = {
        'patients': patients,
        'search_query': search_query,
        'triage_filter': triage_filter,
    }
    return render(request, 'diagnosis/patient_list.html', context)


@login_required
def patient_archived_list(request):
    """List all archived (soft-deleted) patients"""
    patients = Patient.objects.filter(is_deleted=True).annotate(
        visit_count=Count('visits'),
        latest_visit_date=Max('visits__created_at')
    ).order_by('-deleted_at')
    
    context = {
        'patients': patients,
        'is_archived': True,
    }
    return render(request, 'diagnosis/patient_list.html', context)


@login_required
def patient_restore(request, patient_id):
    """Restore archived patient"""
    patient = get_object_or_404(Patient, patient_id=patient_id, is_deleted=True)
    
    if request.method == 'POST':
        patient_name = patient.get_full_name()
        patient.is_deleted = False
        patient.deleted_at = None
        patient.deleted_by = None
        patient.save()
        messages.success(request, f'Patient {patient_name} ({patient_id}) has been restored successfully.')
        return redirect('patient_detail', patient_id=patient_id)
    
    return redirect('patient_archived_list')


@login_required
def patient_delete(request, patient_id):
    """Archive patient (soft delete) - can be recovered later"""
    patient = get_object_or_404(Patient, patient_id=patient_id, is_deleted=False)
    
    if request.method == 'POST':
        patient_name = patient.get_full_name()
        # Soft delete - mark as deleted instead of removing from database
        patient.is_deleted = True
        patient.deleted_at = timezone.now()
        patient.deleted_by = request.user
        patient.save()
        messages.success(request, f'Patient {patient_name} ({patient_id}) has been archived. You can restore it from the archived patients list.')
        return redirect('patient_list')
    
    # GET request - show confirmation page
    context = {
        'patient': patient,
        'visit_count': patient.visits.count(),
    }
    return render(request, 'diagnosis/patient_delete_confirm.html', context)


@login_required
def patient_edit(request, patient_id):
    """Edit patient demographics"""
    patient = get_object_or_404(Patient, patient_id=patient_id)
    
    if request.method == 'POST':
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            messages.success(request, f'Patient {patient.patient_id} updated successfully!')
            return redirect('patient_detail', patient_id=patient.patient_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PatientForm(instance=patient)
    
    context = {
        'form': form,
        'patient': patient,
        'is_edit': True,
    }
    return render(request, 'diagnosis/patient_edit.html', context)


@login_required
def visit_edit(request, patient_id, visit_number):
    """Edit visit data including vitals and labs"""
    patient = get_object_or_404(Patient, patient_id=patient_id)
    visit = get_object_or_404(Visit, patient=patient, visit_number=visit_number)
    
    # Get existing vitals and labs if they exist
    vitals = getattr(visit, 'vitals', None)
    labs = getattr(visit, 'labs', None)
    
    if request.method == 'POST':
        visit_form = VisitForm(request.POST, instance=visit)
        vitals_form = VitalsForm(request.POST, instance=vitals)
        labs_form = LabsForm(request.POST, instance=labs)
        
        if visit_form.is_valid() and vitals_form.is_valid() and labs_form.is_valid():
            try:
                with transaction.atomic():
                    visit_form.save()
                    
                    # Update or create vitals
                    if vitals:
                        vitals_form.save()
                    else:
                        vitals_obj = vitals_form.save(commit=False)
                        vitals_obj.visit = visit
                        vitals_obj.save()
                    
                    # Update or create labs
                    if labs:
                        labs_form.save()
                    else:
                        labs_obj = labs_form.save(commit=False)
                        labs_obj.visit = visit
                        labs_obj.save()
                    
                    messages.success(request, f'Visit #{visit_number} updated successfully!')
                    return redirect('patient_detail', patient_id=patient.patient_id)
                    
            except Exception as e:
                messages.error(request, f'Error updating visit: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        visit_form = VisitForm(instance=visit)
        vitals_form = VitalsForm(instance=vitals)
        labs_form = LabsForm(instance=labs)
    
    context = {
        'visit_form': visit_form,
        'vitals_form': vitals_form,
        'labs_form': labs_form,
        'patient': patient,
        'visit': visit,
        'is_edit': True,
    }
    return render(request, 'diagnosis/visit_edit.html', context)
