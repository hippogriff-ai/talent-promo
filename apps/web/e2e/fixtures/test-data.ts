/**
 * Test Data Fixtures
 *
 * Reusable test data for E2E tests.
 */

export const testResume = {
  text: `
JOHN DOE
Senior Software Engineer | San Francisco, CA
john.doe@email.com | (555) 123-4567 | linkedin.com/in/johndoe

SUMMARY
Experienced software engineer with 8+ years of expertise in full-stack development,
specializing in Python, TypeScript, and cloud infrastructure. Proven track record
of leading teams and delivering scalable solutions.

EXPERIENCE

Senior Software Engineer | TechCorp Inc.
San Francisco, CA | Jan 2020 - Present
- Led development of microservices architecture serving 10M+ daily users
- Implemented CI/CD pipelines reducing deployment time by 70%
- Mentored team of 5 junior developers

Software Engineer | StartupXYZ
Mountain View, CA | Jun 2016 - Dec 2019
- Built real-time data processing pipeline handling 1M events/hour
- Developed RESTful APIs using Python/FastAPI
- Collaborated with cross-functional teams on product features

SKILLS
Languages: Python, TypeScript, JavaScript, Go
Frameworks: React, FastAPI, Node.js, Django
Cloud: AWS, GCP, Docker, Kubernetes
Databases: PostgreSQL, MongoDB, Redis

EDUCATION
B.S. Computer Science | Stanford University | 2016
  `.trim(),
};

export const testJob = {
  url: 'https://example.com/jobs/senior-engineer',
  text: `
Senior Software Engineer

About Us:
We're a fast-growing AI startup revolutionizing the way people work. Our platform
uses cutting-edge machine learning to help professionals be more productive.

Requirements:
- 5+ years of software engineering experience
- Strong proficiency in Python and TypeScript
- Experience with React and modern frontend frameworks
- Familiarity with cloud platforms (AWS/GCP)
- Experience with microservices architecture
- Strong communication and leadership skills

Nice to Have:
- Experience with ML/AI systems
- Contributions to open source projects
- Experience mentoring junior engineers

Benefits:
- Competitive salary ($180K - $250K)
- Equity compensation
- Unlimited PTO
- Remote-first culture
  `.trim(),
};

export const testDiscoveryAnswers = [
  "I led the migration from a monolithic architecture to microservices at TechCorp, which reduced deployment time by 70% and improved system reliability.",
  "At StartupXYZ, I built a real-time event processing system that could handle 1 million events per hour with 99.9% uptime.",
  "I've mentored 5 junior developers, helping them grow into mid-level engineers. I created a structured onboarding program that reduced ramp-up time by 50%.",
];

export const testEditContent = {
  summaryEdit: "Results-driven Senior Software Engineer with 8+ years of experience building scalable distributed systems. Expert in Python, TypeScript, and cloud-native architectures.",
  experienceEdit: "Architected and implemented microservices platform serving 15M+ daily active users with 99.99% uptime",
};
