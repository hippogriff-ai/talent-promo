"""
Job posting retrieval router
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import logging

from ..services.job_scraper import JobScraper, ScraperError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Initialize job scraper
scraper = JobScraper()


class FetchJobRequest(BaseModel):
    """Request model for fetching a single job posting"""
    url: HttpUrl


class BatchFetchRequest(BaseModel):
    """Request model for batch job fetching"""
    urls: List[HttpUrl]


class JobResponse(BaseModel):
    """Response model for job posting"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    warnings: Optional[List[str]] = None


class BatchJobResponse(BaseModel):
    """Response model for batch job fetching"""
    results: List[JobResponse]
    summary: dict


@router.post("/fetch", response_model=JobResponse)
async def fetch_job(request: FetchJobRequest):
    """
    Fetch and parse a single job posting from a URL

    Args:
        request: FetchJobRequest containing the job posting URL

    Returns:
        JobResponse with the parsed job data or error message
    """
    try:
        logger.info(f"Fetching job from URL: {request.url}")

        # Fetch and parse the job posting
        job_data = await scraper.fetch_job(str(request.url))

        return JobResponse(
            success=True,
            data=job_data,
            warnings=[]
        )

    except ScraperError as e:
        logger.error(f"Scraper error for {request.url}: {str(e)}")
        return JobResponse(
            success=False,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching job {request.url}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch job posting: {str(e)}"
        )


@router.post("/batch", response_model=BatchJobResponse)
async def batch_fetch_jobs(request: BatchFetchRequest):
    """
    Fetch multiple job postings in batch

    Args:
        request: BatchFetchRequest containing list of URLs

    Returns:
        BatchJobResponse with results for each URL and summary statistics
    """
    try:
        logger.info(f"Batch fetching {len(request.urls)} job postings")

        results = []
        successful = 0
        failed = 0
        warnings = 0

        for url in request.urls:
            try:
                job_data = await scraper.fetch_job(str(url))
                results.append(JobResponse(
                    success=True,
                    data=job_data,
                    warnings=[]
                ))
                successful += 1
            except ScraperError as e:
                logger.warning(f"Failed to fetch {url}: {str(e)}")
                results.append(JobResponse(
                    success=False,
                    error=str(e)
                ))
                failed += 1
            except Exception as e:
                logger.error(f"Unexpected error for {url}: {str(e)}")
                results.append(JobResponse(
                    success=False,
                    error=f"Unexpected error: {str(e)}"
                ))
                failed += 1

        return BatchJobResponse(
            results=results,
            summary={
                "total": len(request.urls),
                "successful": successful,
                "failed": failed,
                "warnings": warnings
            }
        )

    except Exception as e:
        logger.error(f"Error in batch fetch: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch fetch failed: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for job scraper service"""
    return {"status": "healthy", "service": "job-scraper"}
