"""
Management command to load sample MIMIC-IV-like knowledge cases
"""
from django.core.management.base import BaseCommand
from diagnosis.models import KnowledgeCase
from diagnosis.services import RAGService


class Command(BaseCommand):
    help = 'Load sample MIMIC-IV-like knowledge cases into the database'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Loading sample knowledge cases...'))
        
        # Sample MIMIC-IV-like cases
        sample_cases = [
            {
                'case_id': 'MIMIC-001',
                'summary_text': '''Chief Complaint: Chest pain
Key Symptoms: Severe crushing chest pain radiating to left arm, shortness of breath, diaphoresis
Abnormal Vitals: BP 160/95 mmHg (abnormal), HR 110 bpm (abnormal), RR 24 breaths/min (abnormal), SpO2 92% (abnormal)
Critical Lab Findings: Elevated troponin I (2.5 ng/mL), elevated CK-MB
Relevant Medical History: Hypertension, hyperlipidemia, smoking history
Demographics: 58 year old M
Current Medications: Lisinopril, atorvastatin''',
                'diagnosis': 'Acute Myocardial Infarction (STEMI)',
                'outcome': 'Emergent cardiac catheterization performed, stent placed, patient stable'
            },
            {
                'case_id': 'MIMIC-002',
                'summary_text': '''Chief Complaint: Difficulty breathing
Key Symptoms: Progressive dyspnea, wheezing, chest tightness, cough
Abnormal Vitals: RR 28 breaths/min (abnormal), SpO2 88% (abnormal), HR 105 bpm (abnormal)
Critical Lab Findings: Normal cardiac enzymes, chest X-ray shows hyperinflation
Relevant Medical History: Asthma, seasonal allergies
Demographics: 35 year old F
Current Medications: Albuterol inhaler PRN''',
                'diagnosis': 'Acute Asthma Exacerbation',
                'outcome': 'Treated with nebulizers, steroids, admitted for observation, discharged in stable condition'
            },
            {
                'case_id': 'MIMIC-003',
                'summary_text': '''Chief Complaint: Severe headache
Key Symptoms: Sudden onset severe headache, neck stiffness, photophobia, nausea, vomiting
Abnormal Vitals: BP 145/90 mmHg (abnormal), Temp 101.2°F (abnormal), HR 98 bpm
Critical Lab Findings: Lumbar puncture shows elevated WBC in CSF, elevated protein
Relevant Medical History: No significant past medical history
Demographics: 42 year old M
Current Medications: None reported''',
                'diagnosis': 'Bacterial Meningitis',
                'outcome': 'IV antibiotics started, admitted to ICU, recovered after 2-week treatment'
            },
            {
                'case_id': 'MIMIC-004',
                'summary_text': '''Chief Complaint: Abdominal pain
Key Symptoms: Right lower quadrant pain, nausea, vomiting, fever, anorexia
Abnormal Vitals: Temp 100.8°F (abnormal), HR 95 bpm, BP 125/78 mmHg
Critical Lab Findings: WBC 14,500 (elevated), CT shows appendiceal inflammation
Relevant Medical History: None significant
Demographics: 28 year old F
Current Medications: None reported''',
                'diagnosis': 'Acute Appendicitis',
                'outcome': 'Emergency appendectomy performed, uncomplicated recovery'
            },
            {
                'case_id': 'MIMIC-005',
                'summary_text': '''Chief Complaint: Altered mental status
Key Symptoms: Confusion, lethargy, decreased responsiveness, slurred speech
Abnormal Vitals: BP 95/60 mmHg (abnormal), HR 115 bpm (abnormal), Temp 95.5°F (abnormal), RR 22 breaths/min (abnormal)
Critical Lab Findings: Glucose 45 mg/dL (critically low), normal electrolytes
Relevant Medical History: Type 2 Diabetes Mellitus
Demographics: 68 year old M
Current Medications: Insulin, metformin''',
                'diagnosis': 'Severe Hypoglycemia',
                'outcome': 'IV dextrose administered, mental status improved, insulin regimen adjusted'
            },
            {
                'case_id': 'MIMIC-006',
                'summary_text': '''Chief Complaint: Sudden weakness on left side
Key Symptoms: Left-sided weakness, facial droop, slurred speech, confusion, onset 2 hours ago
Abnormal Vitals: BP 178/102 mmHg (abnormal), HR 88 bpm
Critical Lab Findings: CT head shows hypodense area in right MCA territory
Relevant Medical History: Atrial fibrillation, hypertension
Demographics: 72 year old F
Current Medications: Warfarin, metoprolol''',
                'diagnosis': 'Acute Ischemic Stroke',
                'outcome': 'tPA administered within window, transferred to stroke unit, partial recovery'
            },
            {
                'case_id': 'MIMIC-007',
                'summary_text': '''Chief Complaint: Severe allergic reaction
Key Symptoms: Facial swelling, difficulty breathing, throat tightness, hives, recent bee sting
Abnormal Vitals: BP 85/55 mmHg (abnormal), HR 125 bpm (abnormal), RR 26 breaths/min (abnormal), SpO2 90% (abnormal)
Critical Lab Findings: Not obtained initially due to emergency
Relevant Medical History: Known bee allergy
Demographics: 24 year old M
Current Medications: EpiPen (not used prior to arrival)''',
                'diagnosis': 'Anaphylactic Shock',
                'outcome': 'Epinephrine, antihistamines, steroids given, admitted to ICU, full recovery'
            },
            {
                'case_id': 'MIMIC-008',
                'summary_text': '''Chief Complaint: Diabetic emergency
Key Symptoms: Excessive thirst, frequent urination, fruity breath odor, nausea, vomiting, abdominal pain
Abnormal Vitals: BP 105/70 mmHg, HR 110 bpm (abnormal), RR 28 breaths/min (abnormal)
Critical Lab Findings: Glucose 485 mg/dL, pH 7.15 (acidotic), elevated ketones, anion gap 22
Relevant Medical History: Type 1 Diabetes Mellitus, poor medication compliance
Demographics: 19 year old F
Current Medications: Insulin (inconsistent use)''',
                'diagnosis': 'Diabetic Ketoacidosis (DKA)',
                'outcome': 'IV fluids, insulin drip, electrolyte correction, admitted to ICU, resolved in 48 hours'
            },
            {
                'case_id': 'MIMIC-009',
                'summary_text': '''Chief Complaint: Severe bleeding
Key Symptoms: Vomiting blood, black tarry stools, dizziness, weakness, pale appearance
Abnormal Vitals: BP 88/50 mmHg (abnormal), HR 130 bpm (abnormal), SpO2 94% (abnormal)
Critical Lab Findings: Hgb 7.2 g/dL (low), platelets normal, PT/INR normal
Relevant Medical History: Chronic NSAID use, history of gastric ulcer
Demographics: 55 year old M
Current Medications: Ibuprofen 800mg TID, aspirin''',
                'diagnosis': 'Upper GI Bleeding (Peptic Ulcer)',
                'outcome': 'Blood transfusion, emergent endoscopy with cauterization, PPI therapy, stable'
            },
            {
                'case_id': 'MIMIC-010',
                'summary_text': '''Chief Complaint: Seizure
Key Symptoms: Witnessed tonic-clonic seizure lasting 3 minutes, post-ictal confusion, tongue biting, loss of consciousness
Abnormal Vitals: HR 108 bpm (abnormal), BP 155/92 mmHg (abnormal) post-ictal
Critical Lab Findings: Normal glucose, normal electrolytes, therapeutic phenytoin level
Relevant Medical History: Epilepsy, previous seizures
Demographics: 32 year old M
Current Medications: Phenytoin, previously well-controlled''',
                'diagnosis': 'Breakthrough Seizure (Epilepsy)',
                'outcome': 'Seizure precautions, phenytoin level adjusted, neurology consult, discharged'
            },
            {
                'case_id': 'MIMIC-011',
                'summary_text': '''Chief Complaint: Pneumonia symptoms
Key Symptoms: Fever, productive cough with green sputum, shortness of breath, pleuritic chest pain
Abnormal Vitals: Temp 102.5°F (abnormal), RR 24 breaths/min (abnormal), SpO2 91% (abnormal), HR 102 bpm (abnormal)
Critical Lab Findings: WBC 16,800, chest X-ray shows right lower lobe infiltrate
Relevant Medical History: COPD, smoking history
Demographics: 65 year old M
Current Medications: Tiotropium, albuterol''',
                'diagnosis': 'Community-Acquired Pneumonia',
                'outcome': 'IV antibiotics, supplemental oxygen, admitted to medical ward, improved in 5 days'
            },
            {
                'case_id': 'MIMIC-012',
                'summary_text': '''Chief Complaint: Pulmonary embolism
Key Symptoms: Sudden onset shortness of breath, sharp chest pain worse with breathing, recent long flight
Abnormal Vitals: RR 28 breaths/min (abnormal), SpO2 89% (abnormal), HR 118 bpm (abnormal), BP 110/75 mmHg
Critical Lab Findings: Elevated D-dimer, CT angiography shows bilateral pulmonary emboli
Relevant Medical History: Oral contraceptive use, family history of DVT
Demographics: 31 year old F
Current Medications: Oral contraceptive pills''',
                'diagnosis': 'Acute Pulmonary Embolism',
                'outcome': 'Anticoagulation with heparin, transitioned to warfarin, admitted to telemetry, stable'
            },
        ]
        
        # Initialize RAG service for embeddings
        rag_service = RAGService()
        
        created_count = 0
        updated_count = 0
        
        for case_data in sample_cases:
            # Generate embedding
            embedding = rag_service.generate_embedding(case_data['summary_text'])
            embedding_binary = rag_service.numpy_to_binary(embedding)
            
            # Create or update case
            case, created = KnowledgeCase.objects.update_or_create(
                case_id=case_data['case_id'],
                defaults={
                    'summary_text': case_data['summary_text'],
                    'diagnosis': case_data['diagnosis'],
                    'outcome': case_data['outcome'],
                    'embedding': embedding_binary
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created case: {case.case_id}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated case: {case.case_id}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSummary:'))
        self.stdout.write(self.style.SUCCESS(f'Created: {created_count} cases'))
        self.stdout.write(self.style.SUCCESS(f'Updated: {updated_count} cases'))
        
        # Build FAISS index
        self.stdout.write(self.style.SUCCESS('\nBuilding FAISS index...'))
        knowledge_cases = KnowledgeCase.objects.all()
        rag_service.build_index(knowledge_cases)
        
        self.stdout.write(self.style.SUCCESS('Done! Knowledge base ready.'))
