# Medical Emergency RAG Diagnosis System

A Django-based Retrieval-Augmented Generation (RAG) system for emergency diagnosis and triage using MIMIC-IV-style EHR data.

## Overview

This application implements an AI-powered clinical decision support system that:
- Accepts comprehensive patient data (demographics, vitals, labs, symptoms, history)
- Generates structured clinical summaries
- Retrieves similar historical cases from a MIMIC-IV-like knowledge base using FAISS vector search
- Uses Groq LLM to generate differential diagnoses, triage levels, and medical reasoning
- Provides explainable AI outputs with evidence from retrieved cases

**IMPORTANT: This is a research prototype for educational and research purposes only. It is NOT a medical device and should NOT be used for actual clinical decision-making.**

## Tech Stack

- **Backend**: Django 5.0
- **Database**: SQLite
- **Vector Search**: FAISS (local)
- **Embeddings**: Sentence-Transformers (all-MiniLM-L6-v2)
- **LLM**: Groq API (Llama 3.3, Llama 3.1, Mixtral)
- **Frontend**: Django Templates with modern CSS

## Features

- Patient data intake with comprehensive forms
- Automatic clinical summary generation
- RAG-based diagnosis system with evidence retrieval
- Differential diagnosis (multiple possibilities, not single diagnosis)
- Triage level assignment (Low/Medium/High/Critical)
- Confidence scoring
- Patient history tracking
- Modern, professional UI with futuristic design

## Installation

### Prerequisites

- Python 3.10+
- pip
- Groq API key

### Setup

1. **Clone/Navigate to the project**
   ```bash
   cd /home/akhil/Downloads/temp/med-major
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   
   **Single API Key:**
   ```bash
   export GROQ_API_KEY="your-groq-api-key-here"
   ```
   
   **Multiple API Keys (recommended for automatic fallback):**
   ```bash
   export GROQ_API_KEYS="key1,key2,key3"
   ```
   
   The system supports multiple Groq API keys for automatic fallback when daily quotas are reached. When one key hits its limit, the system automatically switches to the next available key.

4. **Run migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Load sample knowledge base**
   ```bash
   python manage.py load_knowledge_base
   ```
   This will load 12 sample MIMIC-IV-like cases and build the FAISS index.

6. **Create superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   - Main app: http://localhost:8000
   - Admin interface: http://localhost:8000/admin

## Usage

### Adding a New Patient

1. Navigate to "New Patient" from the home page
2. Fill in patient demographics, clinical information, vital signs, and lab results
3. Click "Save and Generate Diagnosis"
4. The system will automatically:
   - Generate a clinical summary
   - Retrieve similar cases
   - Generate differential diagnoses using Groq
   - Display results with triage level and reasoning

### Viewing Patient History

- Click "Patient List" to see all patients
- Click on a patient ID to view detailed information
- View diagnosis history for each patient
- Generate new diagnoses for existing patients

### Knowledge Base Management

The knowledge base contains MIMIC-IV-like cases. To reload or update:

```bash
python manage.py load_knowledge_base
```

## Project Structure

```
med-major/
├── diagnosis/                  # Main Django app
│   ├── models.py              # Database models
│   ├── views.py               # View functions
│   ├── forms.py               # Form definitions
│   ├── urls.py                # URL routing
│   ├── admin.py               # Admin configuration
│   ├── services/              # Service layer
│   │   ├── clinical_summary_generator.py
│   │   ├── rag_service.py
│   │   └── llm_service.py
│   ├── templates/             # HTML templates
│   │   └── diagnosis/
│   └── management/            # Management commands
│       └── commands/
│           └── load_knowledge_base.py
├── med_emergency_rag/         # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── manage.py
├── requirements.txt
└── README.md
```

## Models

- **Patient**: Demographics and clinical data
- **Vitals**: Vital signs (BP, HR, RR, SpO2, Temp)
- **Labs**: Laboratory results
- **ClinicalSummary**: Structured summary with embeddings
- **KnowledgeCase**: MIMIC-IV-like historical cases
- **DiagnosisResult**: Generated diagnoses with reasoning
- **LLMUsage**: Daily quota tracking per model and API key

## Multi-API-Key Fallback System

The system supports automatic fallback across multiple API keys and models to handle daily quota limits:

### Features
- **Multiple API Keys**: Configure multiple Gemini API keys for automatic fallback
- **Model Cascade**: Falls back to different models when quotas are reached
- **Quota Tracking**: Tracks daily usage per model and API key
- **Automatic Retry**: Retries with exponential backoff for transient errors

### Model Cascade Order
1. **llama-3.3-70b-versatile** (1,000 requests/day)
2. **qwen/qwen3-32b** (1,000 requests/day)
3. **llama-3.1-8b-instant** (14,400 requests/day)

### Configuration
Set multiple API keys separated by commas:
```bash
export GROQ_API_KEYS="key1,key2,key3"
```

The system will:
1. Try all API keys for the first model
2. If all keys hit quota, move to next model
3. Repeat until successful or all options exhausted
4. Track usage in database to avoid unnecessary API calls

## Safety Features

- Always provides differential diagnoses (never single diagnosis)
- Expresses uncertainty and limitations
- Includes confidence scores
- Shows retrieved evidence cases
- Prominent disclaimers throughout UI
- Designed for decision support, not autonomous diagnosis

## API Integration

### Groq API with Multi-Key Fallback

The system uses Groq API with intelligent fallback mechanisms:

**Single API Key:**
```bash
export GROQ_API_KEY="your-api-key"
```

**Multiple API Keys (recommended):**
```bash
export GROQ_API_KEYS="key1,key2,key3"
```

### How Fallback Works

When a diagnosis is requested:
1. System tries first model with first API key
2. If quota exhausted, tries next API key with same model
3. If all keys exhausted for a model, moves to next model
4. Process repeats until successful or all options exhausted
5. Usage is tracked in database to prevent unnecessary API calls

The LLM is prompted to:
- Only use retrieved evidence
- Generate multiple differential diagnoses
- Provide medical reasoning
- Assign triage levels
- Express uncertainty

## Development

### Running Tests

```bash
python manage.py test
```

### Admin Interface

Access Django admin at `/admin` to manage:
- Patients
- Knowledge cases
- Diagnoses
- All other models

### Adding More Knowledge Cases

Edit `diagnosis/management/commands/load_knowledge_base.py` and add cases to the `sample_cases` list, then run:

```bash
python manage.py load_knowledge_base
```

## Limitations

- Research prototype only
- Not validated for clinical use
- Requires internet connection for Gemini API
- Local FAISS index (single-machine only)
- SQLite database (not for production scale)

## License

This is a research prototype. Use for educational and research purposes only.
