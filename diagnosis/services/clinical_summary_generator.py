"""
Clinical Summary Generator
Converts raw patient data into structured clinical summary
"""

class ClinicalSummaryGenerator:
    """Generate structured clinical summary from visit data"""
    
    @staticmethod
    def generate(visit, vitals=None, labs=None):
        """
        Generate a structured clinical summary from visit data
        
        Args:
            visit: Visit model instance
            vitals: Vitals model instance (optional)
            labs: Labs model instance (optional)
            
        Returns:
            str: Formatted clinical summary
        """
        patient = visit.patient
        summary_parts = []
        
        # Visit Context
        is_follow_up = visit.visit_type == 'FOLLOW_UP'
        if is_follow_up:
            summary_parts.append(f"**FOLLOW-UP VISIT #{visit.visit_number}**")
            summary_parts.append("This is a return visit for ongoing care.\n")
        else:
            summary_parts.append(f"**INITIAL VISIT**\n")
        
        # Chief Complaint
        summary_parts.append(f"Chief Complaint: {visit.chief_complaint}")
        
        # Key Symptoms
        summary_parts.append(f"Key Symptoms: {visit.symptoms}")
        
        # Previous Visit History (for follow-ups)
        if is_follow_up:
            previous_visits = patient.visits.filter(visit_number__lt=visit.visit_number).order_by('-visit_number')[:2]
            if previous_visits:
                summary_parts.append("\n**PREVIOUS VISIT HISTORY:**")
                for prev_visit in previous_visits:
                    summary_parts.append(f"\nVisit #{prev_visit.visit_number} ({prev_visit.created_at.strftime('%Y-%m-%d')}):")
                    summary_parts.append(f"  - Chief Complaint: {prev_visit.chief_complaint}")
                    
                    # Include previous diagnosis if available
                    prev_diagnosis = prev_visit.diagnosis_results.first()
                    if prev_diagnosis:
                        top_dx = prev_diagnosis.get_top_diagnosis()
                        if top_dx:
                            summary_parts.append(f"  - Previous Diagnosis: {top_dx.get('diagnosis', 'N/A')} ({top_dx.get('likelihood', 0)}% likelihood)")
                        summary_parts.append(f"  - Triage Level: {prev_diagnosis.triage_level}")
                
                summary_parts.append("")  # Empty line for separation
        
        # Abnormal Vitals
        if vitals:
            abnormal_vitals = []
            
            if vitals.blood_pressure_systolic and vitals.blood_pressure_diastolic:
                bp = f"BP {vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic} mmHg"
                if vitals.blood_pressure_systolic > 140 or vitals.blood_pressure_systolic < 90:
                    abnormal_vitals.append(f"{bp} (abnormal)")
                elif vitals.blood_pressure_diastolic > 90 or vitals.blood_pressure_diastolic < 60:
                    abnormal_vitals.append(f"{bp} (abnormal)")
            
            if vitals.heart_rate:
                hr = f"HR {vitals.heart_rate} bpm"
                if vitals.heart_rate > 100 or vitals.heart_rate < 60:
                    abnormal_vitals.append(f"{hr} (abnormal)")
            
            if vitals.respiratory_rate:
                rr = f"RR {vitals.respiratory_rate} breaths/min"
                if vitals.respiratory_rate > 20 or vitals.respiratory_rate < 12:
                    abnormal_vitals.append(f"{rr} (abnormal)")
            
            if vitals.oxygen_saturation:
                spo2 = f"SpO2 {vitals.oxygen_saturation}%"
                if vitals.oxygen_saturation < 95:
                    abnormal_vitals.append(f"{spo2} (abnormal)")
            
            if vitals.temperature:
                temp = f"Temp {vitals.temperature}°F"
                if vitals.temperature > 100.4 or vitals.temperature < 95:
                    abnormal_vitals.append(f"{temp} (abnormal)")
            
            vitals_text = ", ".join(abnormal_vitals) if abnormal_vitals else "All vitals within normal range"
            summary_parts.append(f"Abnormal Vitals: {vitals_text}")
        else:
            summary_parts.append("Abnormal Vitals: No vitals recorded")
        
        # Critical Lab Findings
        if labs and labs.lab_results:
            summary_parts.append(f"Critical Lab Findings: {labs.lab_results}")
        else:
            summary_parts.append("Critical Lab Findings: No labs recorded")
        
        # Relevant Medical History
        medical_history = patient.past_medical_history if patient.past_medical_history else "None reported"
        summary_parts.append(f"Relevant Medical History: {medical_history}")
        
        # Demographics
        summary_parts.append(f"Demographics: {patient.age} year old {patient.sex}")
        
        # Current Medications
        medications = patient.medications if patient.medications else "None reported"
        summary_parts.append(f"Current Medications: {medications}")
        
        # Join all parts
        summary = "\n".join(summary_parts)
        
        return summary
