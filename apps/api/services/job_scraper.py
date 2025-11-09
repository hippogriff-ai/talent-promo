"""
Job scraper service for retrieving job postings from various platforms
"""

from typing import Dict, Optional
from urllib.parse import urlparse
import logging
from datetime import datetime
import re
import asyncio

import requests
from bs4 import BeautifulSoup
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Cache for storing recently fetched jobs (1 hour TTL, max 100 items)
job_cache = TTLCache(maxsize=100, ttl=3600)


class ScraperError(Exception):
    """Custom exception for scraper errors"""
    pass


class JobScraper:
    """Main job scraper class that coordinates platform-specific scrapers"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        self.timeout = 10

    async def fetch_job(self, url: str) -> Dict:
        """
        Fetch and parse a job posting from a URL

        Args:
            url: The URL of the job posting

        Returns:
            Dictionary containing structured job data

        Raises:
            ScraperError: If scraping fails
        """
        # Check cache first
        if url in job_cache:
            logger.info(f"Returning cached result for {url}")
            return job_cache[url]

        # Detect platform
        platform = self._detect_platform(url)
        logger.info(f"Detected platform: {platform} for URL: {url}")

        # Scrape based on platform
        try:
            if platform == "LinkedIn":
                job_data = await self._scrape_linkedin(url)
            elif platform == "Indeed":
                job_data = await self._scrape_indeed(url)
            elif platform == "Glassdoor":
                job_data = await self._scrape_glassdoor(url)
            elif platform == "AngelList":
                job_data = await self._scrape_angellist(url)
            else:
                job_data = await self._scrape_generic(url)

            # Add source URL and metadata
            job_data["sourceUrl"] = url
            job_data["platform"] = platform
            job_data["metadata"] = {
                "retrievedDate": datetime.now().isoformat(),
                "retrievalMethod": "scraper",
                "dataQuality": self._calculate_quality_score(job_data)
            }

            # Cache the result
            job_cache[url] = job_data

            return job_data

        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            raise ScraperError(f"Failed to scrape job posting: {str(e)}")

    def _detect_platform(self, url: str) -> str:
        """Detect the job platform from URL"""
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        if "linkedin.com" in hostname:
            return "LinkedIn"
        elif "indeed.com" in hostname:
            return "Indeed"
        elif "glassdoor.com" in hostname:
            return "Glassdoor"
        elif "wellfound.com" in hostname or "angel.co" in hostname:
            return "AngelList"
        else:
            return "Other"

    async def _scrape_linkedin(self, url: str) -> Dict:
        """Scrape LinkedIn job posting"""
        # Note: LinkedIn heavily uses JavaScript and requires authentication
        # This is a simplified version that demonstrates the structure
        # In production, you'd need to use Playwright or Selenium

        try:
            response = await asyncio.to_thread(
                requests.get, url, headers=self.headers, timeout=self.timeout
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            # Extract job data (simplified - actual selectors may vary)
            job_data = {
                "id": self._generate_id(),
                "title": self._extract_text(soup, ['h1', '.job-title'], "Unknown Title"),
                "jobId": self._extract_job_id_from_url(url),
                "company": {
                    "name": self._extract_text(soup, ['.company-name', '.topcard__org-name-link'], "Unknown Company"),
                    "industry": "",
                    "size": "",
                    "website": "",
                    "logo": "",
                    "description": ""
                },
                "location": {
                    "specificLocation": self._extract_text(soup, ['.job-location', '.topcard__flavor--bullet'], "Remote"),
                    "remote": "remote" in url.lower(),
                    "hybrid": False
                },
                "workLocation": self._determine_work_location(
                    self._extract_text(soup, ['.job-location'], "")
                ),
                "jobType": "Full-time",
                "description": self._extract_text(soup, ['.description__text', '.show-more-less-html'], ""),
                "requirements": [],
                "preferredQualifications": [],
                "benefits": [],
                "salaryRange": None,
                "postedDate": None,
                "closingDate": None,
                "applicationInfo": None
            }

            return job_data

        except Exception as e:
            raise ScraperError(f"LinkedIn scraping failed: {str(e)}")

    async def _scrape_indeed(self, url: str) -> Dict:
        """Scrape Indeed job posting"""
        try:
            response = await asyncio.to_thread(
                requests.get, url, headers=self.headers, timeout=self.timeout
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            # Extract description
            description_elem = soup.find('div', id='jobDescriptionText')
            description = description_elem.get_text(strip=True) if description_elem else ""

            job_data = {
                "id": self._generate_id(),
                "title": self._extract_text(soup, ['h1.jobsearch-JobInfoHeader-title'], "Unknown Title"),
                "jobId": self._extract_job_id_from_url(url),
                "company": {
                    "name": self._extract_text(soup, ['[data-company-name]', '.jobsearch-InlineCompanyRating > div'], "Unknown Company"),
                    "industry": "",
                    "size": "",
                    "website": "",
                    "logo": "",
                    "description": ""
                },
                "location": {
                    "specificLocation": self._extract_text(soup, ['[data-testid="job-location"]', '.jobsearch-JobInfoHeader-subtitle'], "Remote"),
                    "remote": "remote" in description.lower(),
                    "hybrid": "hybrid" in description.lower()
                },
                "workLocation": self._determine_work_location(description),
                "jobType": self._extract_job_type(description),
                "description": description,
                "requirements": self._extract_requirements(description),
                "preferredQualifications": [],
                "benefits": self._extract_benefits(description),
                "salaryRange": self._extract_salary(soup),
                "postedDate": None,
                "closingDate": None,
                "applicationInfo": None
            }

            return job_data

        except Exception as e:
            raise ScraperError(f"Indeed scraping failed: {str(e)}")

    async def _scrape_glassdoor(self, url: str) -> Dict:
        """Scrape Glassdoor job posting"""
        try:
            response = await asyncio.to_thread(
                requests.get, url, headers=self.headers, timeout=self.timeout
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            job_data = {
                "id": self._generate_id(),
                "title": self._extract_text(soup, ['[data-test="job-title"]', 'h1'], "Unknown Title"),
                "jobId": self._extract_job_id_from_url(url),
                "company": {
                    "name": self._extract_text(soup, ['[data-test="employer-name"]'], "Unknown Company"),
                    "industry": "",
                    "size": "",
                    "website": "",
                    "logo": "",
                    "description": ""
                },
                "location": {
                    "specificLocation": self._extract_text(soup, ['[data-test="location"]'], "Remote"),
                    "remote": False,
                    "hybrid": False
                },
                "workLocation": "Onsite",
                "jobType": "Full-time",
                "description": self._extract_text(soup, ['[data-test="jobDescriptionText"]', '.desc'], ""),
                "requirements": [],
                "preferredQualifications": [],
                "benefits": [],
                "salaryRange": None,
                "postedDate": None,
                "closingDate": None,
                "applicationInfo": None
            }

            return job_data

        except Exception as e:
            raise ScraperError(f"Glassdoor scraping failed: {str(e)}")

    async def _scrape_angellist(self, url: str) -> Dict:
        """Scrape AngelList/Wellfound job posting"""
        try:
            response = await asyncio.to_thread(
                requests.get, url, headers=self.headers, timeout=self.timeout
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            job_data = {
                "id": self._generate_id(),
                "title": self._extract_text(soup, ['h1'], "Unknown Title"),
                "jobId": self._extract_job_id_from_url(url),
                "company": {
                    "name": self._extract_text(soup, ['.company-name'], "Unknown Company"),
                    "industry": "",
                    "size": "",
                    "website": "",
                    "logo": "",
                    "description": ""
                },
                "location": {
                    "specificLocation": "Remote",
                    "remote": True,
                    "hybrid": False
                },
                "workLocation": "Remote",
                "jobType": "Full-time",
                "description": self._extract_text(soup, ['.job-description'], ""),
                "requirements": [],
                "preferredQualifications": [],
                "benefits": [],
                "salaryRange": None,
                "postedDate": None,
                "closingDate": None,
                "applicationInfo": None
            }

            return job_data

        except Exception as e:
            raise ScraperError(f"AngelList scraping failed: {str(e)}")

    async def _scrape_generic(self, url: str) -> Dict:
        """Generic scraper for company career pages"""
        try:
            response = await asyncio.to_thread(
                requests.get, url, headers=self.headers, timeout=self.timeout
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            # Try to find common elements
            title = self._extract_text(soup, ['h1', '.job-title', '[class*="title"]'], "Unknown Title")
            description = self._extract_text(soup, ['[class*="description"]', '[class*="details"]', 'main'], "")

            job_data = {
                "id": self._generate_id(),
                "title": title,
                "jobId": self._extract_job_id_from_url(url),
                "company": {
                    "name": self._extract_company_from_url(url),
                    "industry": "",
                    "size": "",
                    "website": f"{urlparse(url).scheme}://{urlparse(url).netloc}",
                    "logo": "",
                    "description": ""
                },
                "location": {
                    "specificLocation": self._extract_text(soup, ['[class*="location"]'], "Unknown"),
                    "remote": "remote" in description.lower(),
                    "hybrid": "hybrid" in description.lower()
                },
                "workLocation": self._determine_work_location(description),
                "jobType": self._extract_job_type(description),
                "description": description,
                "requirements": self._extract_requirements(description),
                "preferredQualifications": [],
                "benefits": self._extract_benefits(description),
                "salaryRange": None,
                "postedDate": None,
                "closingDate": None,
                "applicationInfo": None
            }

            return job_data

        except Exception as e:
            raise ScraperError(f"Generic scraping failed: {str(e)}")

    # Helper methods

    def _extract_text(self, soup: BeautifulSoup, selectors: list, default: str = "") -> str:
        """Extract text from soup using multiple selectors"""
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return default

    def _extract_job_id_from_url(self, url: str) -> str:
        """Extract job ID from URL"""
        # Try to find numeric ID in URL
        match = re.search(r'/(\d+)(?:/|$|\?)', url)
        if match:
            return match.group(1)
        return ""

    def _extract_company_from_url(self, url: str) -> str:
        """Extract company name from URL hostname"""
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        # Remove www. and TLD
        company = re.sub(r'^www\.', '', hostname)
        company = re.sub(r'\.[^.]+$', '', company)
        return company.title()

    def _determine_work_location(self, text: str) -> str:
        """Determine work location type from text"""
        text_lower = text.lower()
        if "remote" in text_lower and "hybrid" not in text_lower:
            return "Remote"
        elif "hybrid" in text_lower:
            return "Hybrid"
        else:
            return "Onsite"

    def _extract_job_type(self, text: str) -> str:
        """Extract job type from description"""
        text_lower = text.lower()
        if "part-time" in text_lower or "part time" in text_lower:
            return "Part-time"
        elif "contract" in text_lower:
            return "Contract"
        elif "intern" in text_lower:
            return "Internship"
        elif "temporary" in text_lower or "temp" in text_lower:
            return "Temporary"
        else:
            return "Full-time"

    def _extract_requirements(self, text: str) -> list:
        """Extract requirements from description text"""
        requirements = []

        # Look for requirements sections
        req_patterns = [
            r'requirements?:?(.*?)(?:preferred|responsibilities|benefits|$)',
            r'qualifications?:?(.*?)(?:preferred|responsibilities|benefits|$)',
            r'must have:?(.*?)(?:nice to have|responsibilities|benefits|$)'
        ]

        for pattern in req_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                req_text = match.group(1)
                # Split by bullet points or newlines
                items = re.split(r'[•\-\*\n]+', req_text)
                for item in items:
                    item = item.strip()
                    if len(item) > 10 and len(item) < 500:  # reasonable length
                        requirements.append({
                            "text": item,
                            "required": True,
                            "category": "other"
                        })
                break

        return requirements[:10]  # Limit to 10 requirements

    def _extract_benefits(self, text: str) -> list:
        """Extract benefits from description text"""
        benefits = []

        benefit_keywords = [
            "health insurance", "dental", "vision", "401k", "pto", "vacation",
            "remote work", "flexible hours", "equity", "stock options",
            "professional development", "tuition", "gym", "wellness"
        ]

        text_lower = text.lower()
        for keyword in benefit_keywords:
            if keyword in text_lower:
                benefits.append({
                    "category": "other",
                    "description": keyword.title()
                })

        return benefits[:15]  # Limit to 15 benefits

    def _extract_salary(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract salary information from soup"""
        salary_selectors = [
            '[data-testid="salaryInfoAndJobType"]',
            '.salary-snippet',
            '[class*="salary"]'
        ]

        salary_text = self._extract_text(soup, salary_selectors)
        if not salary_text:
            return None

        # Try to parse salary range
        # This is a simplified version - production would need more robust parsing
        salary_match = re.search(r'\$?([\d,]+)\s*-\s*\$?([\d,]+)', salary_text)
        if salary_match:
            return {
                "min": int(salary_match.group(1).replace(',', '')),
                "max": int(salary_match.group(2).replace(',', '')),
                "currency": "USD",
                "period": "Year",
                "displayText": salary_text
            }

        return None

    def _calculate_quality_score(self, job_data: Dict) -> float:
        """Calculate data quality score (0-1)"""
        score = 0.0
        weights = {
            "title": 0.2,
            "company": 0.15,
            "description": 0.25,
            "location": 0.1,
            "requirements": 0.15,
            "salary": 0.15
        }

        if job_data.get("title") and job_data["title"] != "Unknown Title":
            score += weights["title"]

        if job_data.get("company", {}).get("name") and job_data["company"]["name"] != "Unknown Company":
            score += weights["company"]

        if job_data.get("description") and len(job_data["description"]) > 100:
            score += weights["description"]

        if job_data.get("location", {}).get("specificLocation"):
            score += weights["location"]

        if job_data.get("requirements") and len(job_data["requirements"]) > 0:
            score += weights["requirements"]

        if job_data.get("salaryRange"):
            score += weights["salary"]

        return min(score, 1.0)

    def _generate_id(self) -> str:
        """Generate a unique ID"""
        from datetime import datetime
        import random
        return f"job-{int(datetime.now().timestamp())}-{random.randint(1000, 9999)}"
