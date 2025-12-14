
### FastAPI Backend README.md
```markdown
# Legal Assistant API

A FastAPI backend for South African legal research and case analysis, providing AI-powered legal assistance.

## Features

- 🏛️ **Legal Q&A** - AI-powered answers based on South African case law
- 📊 **Case Analysis** - Extract legal elements from PDF judgments
- 🔗 **SAFLII Integration** - Access to Southern African Legal Information Institute
- 📚 **Source Management** - Legal source retrieval and citation
- 🚀 **FastAPI** - Modern Python API with automatic docs 

## Tech Stack

- **Framework**: FastAPI
- **AI**: OpenAI GPT-4
- **PDF Processing**: PyPDF2
- **HTTP Client**: Requests
- **Documentation**: Swagger UI & ReDoc

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 5000