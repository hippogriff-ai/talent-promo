"""Sample inputs and expected outputs for prompt tuning.

Each sample contains:
- input: Raw text from EXA (LinkedIn profile or job posting)
- expected: The structured output we want
- source: Where the sample came from

To add new samples:
1. Run the workflow in dev mode
2. Capture the raw EXA output from logs
3. Manually create the expected structured output
"""

# =============================================================================
# LINKEDIN PROFILE SAMPLES
# =============================================================================

PROFILE_SAMPLES = [
    {
        "id": "profile_001",
        "description": "Senior software engineer at FAANG",
        "input": """
John Smith
Senior Software Engineer at Google

San Francisco Bay Area • 500+ connections

About
Passionate software engineer with 8+ years of experience building scalable distributed systems.
Currently leading a team of 5 engineers working on Google Cloud infrastructure.
Strong background in system design, performance optimization, and mentoring junior engineers.
Previously at Facebook and Amazon. Stanford CS grad.

Experience

Senior Software Engineer
Google · Full-time
Jan 2021 - Present · 3 yrs
Mountain View, California

Leading development of distributed storage systems handling petabytes of data.
• Designed and implemented a new caching layer reducing latency by 40%
• Mentored 3 junior engineers, all promoted within 18 months
• Led migration of 50+ services to Kubernetes
Technologies: Go, C++, Kubernetes, Spanner, BigQuery

Software Engineer II
Facebook (Meta) · Full-time
Jun 2018 - Dec 2020 · 2 yrs 7 mos
Menlo Park, California

Built and maintained critical news feed ranking infrastructure.
• Improved feed relevance by 15% through ML model improvements
• Reduced serving latency by 30% through caching optimizations
• On-call rotation for tier-0 service with 99.99% SLA
Technologies: Python, C++, PyTorch, Presto

Software Development Engineer
Amazon · Full-time
Jul 2016 - May 2018 · 1 yr 11 mos
Seattle, Washington

Developed backend services for Prime Video streaming platform.
• Built real-time analytics pipeline processing 1M+ events/second
• Implemented A/B testing framework used by 20+ teams
Technologies: Java, DynamoDB, Lambda, Kinesis

Education

Stanford University
BS, Computer Science
2012 - 2016

Skills
Distributed Systems • System Design • Go • Python • C++ • Kubernetes • AWS •
Machine Learning • Technical Leadership • Mentoring
""",
        "expected": {
            "name": "John Smith",
            "headline": "Senior Software Engineer at Google",
            "summary": "Passionate software engineer with 8+ years of experience building scalable distributed systems. Currently leading a team of 5 engineers working on Google Cloud infrastructure. Strong background in system design, performance optimization, and mentoring junior engineers. Previously at Facebook and Amazon. Stanford CS grad.",
            "location": "San Francisco Bay Area",
            "experience": [
                {
                    "company": "Google",
                    "position": "Senior Software Engineer",
                    "location": "Mountain View, California",
                    "start_date": "Jan 2021",
                    "end_date": None,
                    "is_current": True,
                    "achievements": [
                        "Designed and implemented a new caching layer reducing latency by 40%",
                        "Mentored 3 junior engineers, all promoted within 18 months",
                        "Led migration of 50+ services to Kubernetes"
                    ],
                    "technologies": ["Go", "C++", "Kubernetes", "Spanner", "BigQuery"],
                    "description": "Leading development of distributed storage systems handling petabytes of data."
                },
                {
                    "company": "Facebook (Meta)",
                    "position": "Software Engineer II",
                    "location": "Menlo Park, California",
                    "start_date": "Jun 2018",
                    "end_date": "Dec 2020",
                    "is_current": False,
                    "achievements": [
                        "Improved feed relevance by 15% through ML model improvements",
                        "Reduced serving latency by 30% through caching optimizations",
                        "On-call rotation for tier-0 service with 99.99% SLA"
                    ],
                    "technologies": ["Python", "C++", "PyTorch", "Presto"],
                    "description": "Built and maintained critical news feed ranking infrastructure."
                },
                {
                    "company": "Amazon",
                    "position": "Software Development Engineer",
                    "location": "Seattle, Washington",
                    "start_date": "Jul 2016",
                    "end_date": "May 2018",
                    "is_current": False,
                    "achievements": [
                        "Built real-time analytics pipeline processing 1M+ events/second",
                        "Implemented A/B testing framework used by 20+ teams"
                    ],
                    "technologies": ["Java", "DynamoDB", "Lambda", "Kinesis"],
                    "description": "Developed backend services for Prime Video streaming platform."
                }
            ],
            "education": [
                {
                    "institution": "Stanford University",
                    "degree": "BS",
                    "field_of_study": "Computer Science",
                    "start_date": "2012",
                    "end_date": "2016"
                }
            ],
            "skills": [
                "Distributed Systems", "System Design", "Go", "Python", "C++",
                "Kubernetes", "AWS", "Machine Learning", "Technical Leadership", "Mentoring"
            ],
            "certifications": []
        }
    },
    {
        "id": "profile_002",
        "description": "Product manager transitioning from engineering",
        "input": """
Sarah Chen
Product Manager at Stripe | Ex-Engineer

New York City Metropolitan Area • 800+ connections

About
Product manager with a unique technical background. After 4 years as a software engineer,
I transitioned to product to combine my love of building with my passion for understanding
user needs. I specialize in developer tools and API products.

Current focus: Making payments simple for platforms and marketplaces.

Experience

Product Manager
Stripe · Full-time
Mar 2022 - Present · 2 yrs
San Francisco, CA (Remote from NYC)

Leading product for Stripe Connect, serving 100k+ platforms.
• Launched new payout scheduling feature, driving $50M ARR
• Improved dashboard UX, increasing self-serve resolution by 35%
• Collaborated with 3 engineering teams across 2 time zones

Senior Software Engineer
Dropbox · Full-time
Aug 2019 - Feb 2022 · 2 yrs 7 mos
San Francisco, California

Tech lead for file sync team.
• Architected new sync protocol reducing conflict rate by 60%
• Led team of 4 engineers
• Owned technical design for iOS/Android clients
Python, Go, SQLite, Mobile Development

Software Engineer
Palantir Technologies · Full-time
Jul 2017 - Jul 2019 · 2 yrs 1 mo
Palo Alto, California

Backend engineer on data integration platform.
• Built ETL pipelines processing 10TB+ daily
• Developed custom query optimization layer
Java, Spark, Hadoop

Education

MIT
MEng, Computer Science
2015 - 2017

UC Berkeley
BS, EECS
2011 - 2015

Certifications
AWS Solutions Architect Associate
Pragmatic Marketing Certified - Level III

Skills
Product Management • Technical Product Management • API Design •
Python • Go • SQL • Agile • User Research • Data Analysis
""",
        "expected": {
            "name": "Sarah Chen",
            "headline": "Product Manager at Stripe | Ex-Engineer",
            "summary": "Product manager with a unique technical background. After 4 years as a software engineer, I transitioned to product to combine my love of building with my passion for understanding user needs. I specialize in developer tools and API products. Current focus: Making payments simple for platforms and marketplaces.",
            "location": "New York City Metropolitan Area",
            "experience": [
                {
                    "company": "Stripe",
                    "position": "Product Manager",
                    "location": "San Francisco, CA (Remote from NYC)",
                    "start_date": "Mar 2022",
                    "end_date": None,
                    "is_current": True,
                    "achievements": [
                        "Launched new payout scheduling feature, driving $50M ARR",
                        "Improved dashboard UX, increasing self-serve resolution by 35%",
                        "Collaborated with 3 engineering teams across 2 time zones"
                    ],
                    "technologies": [],
                    "description": "Leading product for Stripe Connect, serving 100k+ platforms."
                },
                {
                    "company": "Dropbox",
                    "position": "Senior Software Engineer",
                    "location": "San Francisco, California",
                    "start_date": "Aug 2019",
                    "end_date": "Feb 2022",
                    "is_current": False,
                    "achievements": [
                        "Architected new sync protocol reducing conflict rate by 60%",
                        "Led team of 4 engineers",
                        "Owned technical design for iOS/Android clients"
                    ],
                    "technologies": ["Python", "Go", "SQLite", "Mobile Development"],
                    "description": "Tech lead for file sync team."
                },
                {
                    "company": "Palantir Technologies",
                    "position": "Software Engineer",
                    "location": "Palo Alto, California",
                    "start_date": "Jul 2017",
                    "end_date": "Jul 2019",
                    "is_current": False,
                    "achievements": [
                        "Built ETL pipelines processing 10TB+ daily",
                        "Developed custom query optimization layer"
                    ],
                    "technologies": ["Java", "Spark", "Hadoop"],
                    "description": "Backend engineer on data integration platform."
                }
            ],
            "education": [
                {
                    "institution": "MIT",
                    "degree": "MEng",
                    "field_of_study": "Computer Science",
                    "start_date": "2015",
                    "end_date": "2017"
                },
                {
                    "institution": "UC Berkeley",
                    "degree": "BS",
                    "field_of_study": "EECS",
                    "start_date": "2011",
                    "end_date": "2015"
                }
            ],
            "skills": [
                "Product Management", "Technical Product Management", "API Design",
                "Python", "Go", "SQL", "Agile", "User Research", "Data Analysis"
            ],
            "certifications": [
                "AWS Solutions Architect Associate",
                "Pragmatic Marketing Certified - Level III"
            ]
        }
    }
]

# =============================================================================
# JOB POSTING SAMPLES
# =============================================================================

JOB_SAMPLES = [
    {
        "id": "job_001",
        "description": "Senior SWE role at fintech startup",
        "input": """
Senior Software Engineer - Backend
Acme Payments | San Francisco, CA (Hybrid)

About Acme Payments
Acme is a fast-growing fintech startup building the next generation of payment infrastructure.
We process $10B+ annually and are backed by Sequoia and a]6z. Join us to shape the future of money movement.

About the Role
We're looking for a Senior Software Engineer to join our Payments Core team. You'll own critical
infrastructure that processes millions of transactions daily. This is a high-impact role where
you'll work closely with product and design to build delightful developer experiences.

What You'll Do
• Design and build scalable microservices handling 10k+ requests/second
• Own the full lifecycle from design to deployment to monitoring
• Mentor junior engineers and contribute to our engineering culture
• Collaborate with product managers to define technical requirements
• Participate in on-call rotation for production systems

Requirements
• 5+ years of software engineering experience
• Strong proficiency in Go, Python, or Java
• Experience with distributed systems and microservices architecture
• Familiarity with cloud platforms (AWS preferred)
• Experience with relational databases (PostgreSQL)
• Strong communication skills and ability to work cross-functionally
• BS/MS in Computer Science or equivalent experience

Nice to Have
• Experience in fintech or payments industry
• Knowledge of Kubernetes and container orchestration
• Experience with event-driven architectures (Kafka, RabbitMQ)
• Contributions to open-source projects
• Experience with PCI compliance

Tech Stack
Go, Python, PostgreSQL, Redis, Kafka, Kubernetes, AWS, Terraform, Datadog

Benefits
• Competitive salary: $180,000 - $250,000 + equity
• Health, dental, vision insurance (100% covered)
• Unlimited PTO
• $2,000 annual learning budget
• 401(k) with 4% match
• Hybrid work: 3 days in office
• Catered lunches, snacks, and coffee

Acme Payments is an equal opportunity employer.
""",
        "expected": {
            "title": "Senior Software Engineer - Backend",
            "company_name": "Acme Payments",
            "location": "San Francisco, CA (Hybrid)",
            "description": "We're looking for a Senior Software Engineer to join our Payments Core team. You'll own critical infrastructure that processes millions of transactions daily. This is a high-impact role where you'll work closely with product and design to build delightful developer experiences.",
            "work_type": "hybrid",
            "job_type": "full-time",
            "experience_level": "Senior",
            "requirements": [
                "5+ years of software engineering experience",
                "Strong proficiency in Go, Python, or Java",
                "Experience with distributed systems and microservices architecture",
                "Familiarity with cloud platforms (AWS preferred)",
                "Experience with relational databases (PostgreSQL)",
                "Strong communication skills and ability to work cross-functionally",
                "BS/MS in Computer Science or equivalent experience"
            ],
            "preferred_qualifications": [
                "Experience in fintech or payments industry",
                "Knowledge of Kubernetes and container orchestration",
                "Experience with event-driven architectures (Kafka, RabbitMQ)",
                "Contributions to open-source projects",
                "Experience with PCI compliance"
            ],
            "responsibilities": [
                "Design and build scalable microservices handling 10k+ requests/second",
                "Own the full lifecycle from design to deployment to monitoring",
                "Mentor junior engineers and contribute to our engineering culture",
                "Collaborate with product managers to define technical requirements",
                "Participate in on-call rotation for production systems"
            ],
            "tech_stack": [
                "Go", "Python", "PostgreSQL", "Redis", "Kafka",
                "Kubernetes", "AWS", "Terraform", "Datadog"
            ],
            "benefits": [
                "Competitive salary: $180,000 - $250,000 + equity",
                "Health, dental, vision insurance (100% covered)",
                "Unlimited PTO",
                "$2,000 annual learning budget",
                "401(k) with 4% match",
                "Hybrid work: 3 days in office",
                "Catered lunches, snacks, and coffee"
            ],
            "salary_range": "$180,000 - $250,000"
        }
    },
    {
        "id": "job_002",
        "description": "Staff ML engineer at AI company",
        "input": """
Staff Machine Learning Engineer
Anthropic | San Francisco, CA

Anthropic is an AI safety company working to build reliable, interpretable, and steerable AI systems.
Our mission is to develop AI that is safe and beneficial. We're a team of researchers and engineers
who believe in taking a rigorous, research-driven approach to AI safety.

The Role
As a Staff Machine Learning Engineer, you'll work on our core model training infrastructure and
help scale our systems to train frontier AI models. You'll collaborate closely with researchers
to turn research ideas into production systems.

Responsibilities
- Design and implement distributed training systems for large language models
- Optimize training efficiency and reduce costs through algorithmic and systems improvements
- Build tools for experiment tracking, debugging, and analysis
- Collaborate with researchers to implement and scale new training techniques
- Contribute to our internal ML platform used by 50+ researchers
- Drive technical decisions and mentor other engineers

Qualifications

Required:
- 7+ years of experience in software engineering, with 4+ years in ML infrastructure
- Deep expertise in PyTorch and distributed training (FSDP, DeepSpeed, or similar)
- Experience training large models (1B+ parameters)
- Strong systems engineering skills (Linux, networking, CUDA)
- Track record of shipping production ML systems
- MS or PhD in CS, ML, or related field (or equivalent experience)

Preferred:
- Experience with LLM training and RLHF
- Contributions to major ML frameworks or libraries
- Publications in ML systems (MLSys, OSDI, etc.)
- Experience with TPU/custom accelerator training

Compensation
$350,000 - $500,000 base salary + significant equity
This range is for the SF Bay Area. Remote candidates in the US may have adjusted ranges.

Benefits
- Comprehensive health coverage
- Generous equity package
- Flexible work arrangements
- Learning and development budget
- Team offsites and events
""",
        "expected": {
            "title": "Staff Machine Learning Engineer",
            "company_name": "Anthropic",
            "location": "San Francisco, CA",
            "description": "As a Staff Machine Learning Engineer, you'll work on our core model training infrastructure and help scale our systems to train frontier AI models. You'll collaborate closely with researchers to turn research ideas into production systems.",
            "work_type": "hybrid",
            "job_type": "full-time",
            "experience_level": "Staff",
            "requirements": [
                "7+ years of experience in software engineering, with 4+ years in ML infrastructure",
                "Deep expertise in PyTorch and distributed training (FSDP, DeepSpeed, or similar)",
                "Experience training large models (1B+ parameters)",
                "Strong systems engineering skills (Linux, networking, CUDA)",
                "Track record of shipping production ML systems",
                "MS or PhD in CS, ML, or related field (or equivalent experience)"
            ],
            "preferred_qualifications": [
                "Experience with LLM training and RLHF",
                "Contributions to major ML frameworks or libraries",
                "Publications in ML systems (MLSys, OSDI, etc.)",
                "Experience with TPU/custom accelerator training"
            ],
            "responsibilities": [
                "Design and implement distributed training systems for large language models",
                "Optimize training efficiency and reduce costs through algorithmic and systems improvements",
                "Build tools for experiment tracking, debugging, and analysis",
                "Collaborate with researchers to implement and scale new training techniques",
                "Contribute to our internal ML platform used by 50+ researchers",
                "Drive technical decisions and mentor other engineers"
            ],
            "tech_stack": [
                "PyTorch", "FSDP", "DeepSpeed", "CUDA", "Linux"
            ],
            "benefits": [
                "Comprehensive health coverage",
                "Generous equity package",
                "Flexible work arrangements",
                "Learning and development budget",
                "Team offsites and events"
            ],
            "salary_range": "$350,000 - $500,000"
        }
    }
]

# =============================================================================
# GAP ANALYSIS SAMPLES
# =============================================================================

GAP_ANALYSIS_SAMPLES = [
    {
        "id": "gap_001",
        "description": "Profile 001 applying to Job 001",
        "input": {
            "profile": PROFILE_SAMPLES[0]["expected"],
            "job": JOB_SAMPLES[0]["expected"]
        },
        "expected": {
            "strengths": [
                "8+ years of experience exceeds the 5+ requirement",
                "Strong Go proficiency (Google experience)",
                "Deep distributed systems experience (Google Cloud, Spanner)",
                "AWS experience from Amazon role",
                "PostgreSQL experience implied from Presto/data systems work",
                "Leadership/mentoring experience (led team of 5, mentored 3 engineers)",
                "Kubernetes expertise (led migration of 50+ services)"
            ],
            "gaps": [
                "No direct fintech/payments industry experience",
                "Redis not explicitly mentioned in profile",
                "Kafka experience not explicitly mentioned",
                "PCI compliance experience not mentioned"
            ],
            "recommended_emphasis": [
                "Highlight the caching layer design at Google (relevant to payment performance)",
                "Emphasize scale of systems worked on (petabytes, millions of requests)",
                "Focus on real-time processing experience from Amazon Kinesis work",
                "Showcase cross-functional collaboration and mentoring"
            ],
            "transferable_skills": [
                "Building high-throughput distributed systems → payment processing",
                "Latency optimization (40% reduction) → transaction performance",
                "On-call for 99.99% SLA services → payment reliability",
                "Data pipeline experience → payment data flows"
            ],
            "keywords_to_include": [
                "microservices", "distributed systems", "Go", "Python",
                "Kubernetes", "AWS", "PostgreSQL", "high availability",
                "scalability", "mentoring", "technical leadership"
            ],
            "potential_concerns": [
                "Profile doesn't mention fintech - may need to address in cover letter",
                "No explicit mention of event-driven architecture experience"
            ]
        }
    }
]


def get_profile_samples():
    """Get all profile extraction samples."""
    return PROFILE_SAMPLES


def get_job_samples():
    """Get all job extraction samples."""
    return JOB_SAMPLES


def get_gap_analysis_samples():
    """Get all gap analysis samples."""
    return GAP_ANALYSIS_SAMPLES
