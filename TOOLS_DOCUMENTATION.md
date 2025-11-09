# Talent Application Tools Documentation

## Overview

This project implements two essential tools for a resume application system:

1. **Resume Document Parser** - Parses PDF/DOCX resumes into structured JSON
2. **Job Posting Retriever** - Extracts job posting data from various platforms

## Tool 1: Resume Document Parser

### Features

- ✅ Accepts PDF and DOCX file uploads via web UI
- ✅ Drag-and-drop file upload interface
- ✅ File validation (type and 5MB size limit)
- ✅ Real-time parsing progress feedback
- ✅ Extracts structured data into comprehensive JSON format
- ✅ Stores parsed data in IndexedDB (with localStorage fallback)
- ✅ Collapsible, formatted results display
- ✅ Copy-to-clipboard functionality for parsed JSON
- ✅ Confidence scoring for parse quality
- ✅ XSS prevention and input sanitization

### Usage

#### Web Interface

1. Navigate to `/upload` in the web application
2. Select the "Resume Parser" tab
3. Drag and drop a PDF or DOCX file, or click to browse
4. Click "Parse Resume" to process the file
5. View the structured results in the right panel
6. Toggle between "Structured" and "JSON" views
7. Copy the JSON data using the "Copy JSON" button
8. Upload another resume or save the current results

#### Programmatic Usage

```typescript
import { parseResumeFile } from "@/app/utils/parsers/resumeParser";
import { saveResume } from "@/app/utils/storage/resumeStorage";

// Parse a resume file
const parsedResume = await parseResumeFile(file);

// Save to storage
await saveResume(parsedResume);

// Retrieve later
const resume = await getResume(parsedResume.id);
```

### Data Schema

The parser extracts the following structured data:

- **Personal Information**: name, email, phone, location, LinkedIn, portfolio URLs
- **Professional Summary**: brief overview/objective
- **Work Experience**: companies, positions, dates, achievements, technologies
- **Education**: institutions, degrees, fields, dates, GPA, honors
- **Skills**: categorized skills with proficiency levels
- **Certifications**: names, issuers, dates, credentials
- **Projects**: names, descriptions, roles, technologies
- **Languages**: names and proficiency levels
- **References**: contact information

### Technical Implementation

- **PDF Parsing**: Uses `pdfjs-dist` for PDF text extraction
- **DOCX Parsing**: Uses `mammoth.js` for Word document processing
- **Storage**: IndexedDB via `idb` library with localStorage fallback
- **Text Processing**: Intelligent section detection and data extraction
- **Security**: DOMPurify for XSS prevention

### File Size Limit

Maximum file size: **5MB**

### Supported Formats

- PDF (.pdf)
- Microsoft Word (.docx)

---

## Tool 2: Job Posting Retriever

### Features

- ✅ Accepts job posting URLs from various platforms
- ✅ URL validation and platform detection
- ✅ Batch processing for multiple URLs
- ✅ Real-time fetching status
- ✅ Structured job data extraction
- ✅ Result caching (1-hour TTL)
- ✅ Recent URLs history
- ✅ Side-by-side comparison view
- ✅ Copy-to-clipboard functionality
- ✅ Export capabilities

### Supported Platforms

- LinkedIn (linkedin.com)
- Indeed (indeed.com)
- Glassdoor (glassdoor.com)
- AngelList/Wellfound (wellfound.com, angel.co)
- Company career pages (generic scraper)

### Usage

#### Web Interface

1. Navigate to `/upload` in the web application
2. Select the "Job Retriever" tab
3. Enter a job posting URL
4. Click "Fetch Job" to retrieve and parse
5. View the structured job data
6. For batch processing:
   - Toggle to "Batch Processing" mode
   - Add multiple URLs one at a time
   - Click "Fetch N Jobs" to process all

#### API Endpoints

##### Fetch Single Job

```bash
POST /jobs/fetch
Content-Type: application/json

{
  "url": "https://www.linkedin.com/jobs/view/12345"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "job-1234567890-5678",
    "title": "Senior Software Engineer",
    "company": {
      "name": "Tech Company",
      "industry": "Technology",
      ...
    },
    "location": {
      "specificLocation": "San Francisco, CA",
      "remote": false,
      "hybrid": true
    },
    "workLocation": "Hybrid",
    "jobType": "Full-time",
    "description": "...",
    "requirements": [...],
    "salaryRange": {
      "min": 120000,
      "max": 180000,
      "currency": "USD",
      "period": "Year"
    },
    ...
  },
  "warnings": []
}
```

##### Batch Fetch Jobs

```bash
POST /jobs/batch
Content-Type: application/json

{
  "urls": [
    "https://www.linkedin.com/jobs/view/12345",
    "https://www.indeed.com/viewjob?jk=67890"
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "success": true,
      "data": {...}
    },
    {
      "success": false,
      "error": "Failed to fetch job posting"
    }
  ],
  "summary": {
    "total": 2,
    "successful": 1,
    "failed": 1,
    "warnings": 0
  }
}
```

### Data Schema

The retriever extracts:

- **Job Details**: title, job ID, experience level
- **Company Information**: name, industry, size, website, description
- **Location**: specific location, remote/hybrid/onsite designation
- **Job Type**: Full-time, Part-time, Contract, Internship, Temporary
- **Description**: Full job description text
- **Responsibilities**: Bulleted list of key responsibilities
- **Requirements**: Required and preferred qualifications (categorized)
- **Benefits**: Health, financial, time-off, and other perks
- **Salary Range**: Min/max salary with currency and period
- **Dates**: Posted date, closing date
- **Application Info**: Method, URL, email, instructions
- **Metadata**: Retrieval date, method, data quality score

### Technical Implementation

- **Backend**: FastAPI with async request handling
- **Scraping**: BeautifulSoup4 + requests for HTML parsing
- **Caching**: TTLCache (1-hour expiration, 100-item capacity)
- **Platform Detection**: URL parsing and hostname matching
- **Rate Limiting**: Respectful scraping with delays
- **Error Handling**: Graceful degradation with detailed error messages

### Caching

Retrieved job postings are cached for **1 hour** to improve performance and reduce load on job posting sites.

---

## Installation & Setup

### Prerequisites

- Node.js 18+ and pnpm
- Python 3.11+
- Git

### Frontend Setup

```bash
# Navigate to web app
cd apps/web

# Install dependencies
pnpm install

# Run development server
pnpm dev
```

The web app will be available at `http://localhost:3000`

### Backend Setup

```bash
# Navigate to API
cd apps/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run API server
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

---

## Testing

### Resume Parser Tests

Test cases include:
- File type validation (PDF, DOCX, invalid types)
- File size validation (under/over 5MB limit)
- PDF text extraction
- DOCX text extraction
- Personal info extraction (email, phone, LinkedIn)
- Work experience parsing
- Education parsing
- Skills extraction
- IndexedDB storage operations
- localStorage fallback
- Error handling for corrupted files

### Job Retriever Tests

Test cases include:
- URL validation (valid, invalid, malformed)
- Platform detection (LinkedIn, Indeed, Glassdoor, etc.)
- Data extraction accuracy per platform
- Batch processing
- Cache operations
- Error recovery
- Rate limiting compliance
- Cross-platform consistency

---

## Security Considerations

1. **XSS Prevention**: All user-generated content is sanitized using DOMPurify
2. **Input Validation**: Strict file type and size validation
3. **URL Validation**: Only valid HTTP/HTTPS URLs accepted
4. **CORS**: Configured for localhost development
5. **File Sanitization**: File contents validated beyond extension checking
6. **Rate Limiting**: Implemented on backend to prevent abuse

---

## Performance

### Resume Parser
- **Average parse time**: < 3 seconds for typical resume
- **UI responsiveness**: < 100ms for user interactions
- **Storage operations**: < 500ms

### Job Retriever
- **Average retrieval**: < 5 seconds per URL
- **Cache hit**: < 100ms
- **Batch processing**: Concurrent with progress tracking

---

## Architecture

### Frontend Stack
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: TailwindCSS
- **Storage**: IndexedDB via `idb`
- **PDF**: pdfjs-dist
- **DOCX**: mammoth.js
- **Security**: DOMPurify

### Backend Stack
- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Scraping**: BeautifulSoup4, requests
- **Caching**: cachetools
- **Validation**: Pydantic

---

## Error Handling

Both tools implement comprehensive error handling:

- **File Upload Errors**: Clear messages for invalid types, sizes, corrupted files
- **Parsing Errors**: Graceful degradation with partial results and warnings
- **Network Errors**: Retry mechanisms and timeout handling
- **Storage Errors**: Fallback mechanisms with user notification
- **Scraping Errors**: Platform-specific error messages

---

## Future Enhancements

- [ ] Support for additional file formats (RTF, TXT)
- [ ] Machine learning for improved parsing accuracy
- [ ] Multi-language resume support
- [ ] API authentication and rate limiting
- [ ] Job posting change detection
- [ ] Resume-to-job matching algorithm
- [ ] Export to multiple formats (CSV, Excel)
- [ ] Cloud storage integration
- [ ] Mobile responsive improvements
- [ ] Accessibility (WCAG 2.1 AA compliance)

---

## License

This project is part of the Talent Promo application system.

---

## Support

For issues or questions, please contact the development team or create an issue in the project repository.
