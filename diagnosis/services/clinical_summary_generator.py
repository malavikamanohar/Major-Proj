"""
Clinical Summary Generator
Converts raw patient data into structured clinical summary
"""

class ClinicalSummaryGenerator:
    """Generate structured clinical summary from patient data"""
    
    @staticmethod
    def generate(patient, vitals=None, labs=None):
        """
        Generate a structured clinical summary from patient data
        
        Args:
            patient: Patient model instance
            vitals: Vitals model instance (optional)
            labs: Labs model instance (optional)
            
        Returns:
            str: Formatted clinical summary
        """
        summary_parts = []
        
        # Chief Complaint
        summary_parts.append(f"Chief Complaint: {patient.chief_complaint}")
        
        # Key Symptoms
        summary_parts.append(f"Key Symptoms: {patient.symptoms}")
        
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
