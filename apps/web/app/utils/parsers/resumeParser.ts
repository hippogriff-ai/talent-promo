/**
 * Resume Parser
 * Converts raw text into structured resume data
 */

import type { ParsedResume, PersonalInfo, WorkExperience, Education, Skill, Certification, Project, Language } from '@/app/types/resume';

const PARSE_VERSION = '1.0.0';

/**
 * Main function to parse a resume file
 */
export async function parseResumeFile(file: File): Promise<ParsedResume> {
  // Only run on client side
  if (typeof window === 'undefined') {
    throw new Error('Resume parsing can only be done on the client side');
  }

  // Dynamic imports to avoid SSR issues
  const [{ parsePDF, isPDF }, { parseDOCX, isDOCX }] = await Promise.all([
    import('./pdfParser'),
    import('./docxParser')
  ]);

  // Extract raw text based on file type
  let rawText: string;

  if (isPDF(file)) {
    const pdfResult = await parsePDF(file);
    rawText = pdfResult.text;
  } else if (isDOCX(file)) {
    const docxResult = await parseDOCX(file);
    rawText = docxResult.text;
  } else {
    throw new Error('Unsupported file format. Only PDF and DOCX files are supported.');
  }

  if (!rawText || rawText.trim().length === 0) {
    throw new Error('No text content found in the document');
  }

  // Parse the text into structured data
  const parsedData = parseResumeText(rawText);

  return {
    id: generateId(),
    ...parsedData,
    rawText,
    metadata: {
      fileName: file.name,
      fileSize: file.size,
      fileType: file.type,
      parsedDate: new Date().toISOString(),
      parseVersion: PARSE_VERSION,
      confidence: calculateConfidence(parsedData),
    },
  };
}

/**
 * Parse raw text into structured resume data
 */
function parseResumeText(text: string): Omit<ParsedResume, 'id' | 'rawText' | 'metadata'> {
  const lines = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);

  return {
    personalInfo: extractPersonalInfo(text, lines),
    summary: extractSummary(text, lines),
    workExperience: extractWorkExperience(text, lines),
    education: extractEducation(text, lines),
    skills: extractSkills(text, lines),
    certifications: extractCertifications(text, lines),
    projects: extractProjects(text, lines),
    languages: extractLanguages(text, lines),
    references: [],
  };
}

/**
 * Extract personal information
 */
function extractPersonalInfo(text: string, lines: string[]): PersonalInfo {
  const emailRegex = /[\w.-]+@[\w.-]+\.\w+/;
  const phoneRegex = /(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/;
  const linkedinRegex = /linkedin\.com\/in\/[\w-]+/i;

  const email = text.match(emailRegex)?.[0];
  const phone = text.match(phoneRegex)?.[0];
  const linkedinMatch = text.match(linkedinRegex)?.[0];
  const linkedinUrl = linkedinMatch ? `https://${linkedinMatch}` : undefined;

  // Try to extract name from first few lines
  const potentialName = lines[0] || '';
  const name = potentialName.length > 3 && potentialName.length < 50 ? potentialName : 'Unknown';

  return {
    name,
    email,
    phone,
    linkedinUrl,
  };
}

/**
 * Extract professional summary
 */
function extractSummary(text: string, lines: string[]): string | undefined {
  const summaryKeywords = ['summary', 'profile', 'about', 'objective', 'overview'];
  const lowerText = text.toLowerCase();

  for (const keyword of summaryKeywords) {
    const index = lowerText.indexOf(keyword);
    if (index !== -1) {
      // Try to extract text after the keyword
      const afterKeyword = text.substring(index);
      const nextSectionMatch = afterKeyword.match(/\n\n(EXPERIENCE|EDUCATION|SKILLS|WORK)/i);

      if (nextSectionMatch && nextSectionMatch.index) {
        const summary = afterKeyword.substring(0, nextSectionMatch.index).trim();
        // Remove the keyword itself from the beginning
        return summary.replace(new RegExp(`^${keyword}`, 'i'), '').trim();
      }
    }
  }

  return undefined;
}

/**
 * Extract work experience
 */
function extractWorkExperience(text: string, lines: string[]): WorkExperience[] {
  const experiences: WorkExperience[] = [];
  const experienceKeywords = ['experience', 'work history', 'employment', 'professional experience'];
  const dateRegex = /(\d{4}|present|current)/i;

  // Find the experience section
  const lowerText = text.toLowerCase();
  let experienceStartIndex = -1;

  for (const keyword of experienceKeywords) {
    const index = lowerText.indexOf(keyword);
    if (index !== -1) {
      experienceStartIndex = index;
      break;
    }
  }

  if (experienceStartIndex === -1) {
    return experiences;
  }

  // Extract experience section text
  const afterExperience = text.substring(experienceStartIndex);
  const endMatch = afterExperience.match(/\n\n(EDUCATION|SKILLS|CERTIFICATIONS|PROJECTS)/i);
  const experienceText = endMatch && endMatch.index
    ? afterExperience.substring(0, endMatch.index)
    : afterExperience;

  // Simple parsing - look for company and date patterns
  const experienceLines = experienceText.split('\n').filter(l => l.trim().length > 0);

  let currentExp: Partial<WorkExperience> | null = null;

  for (let i = 0; i < experienceLines.length; i++) {
    const line = experienceLines[i].trim();

    // Check if line contains a date (likely a position/company line)
    if (dateRegex.test(line)) {
      if (currentExp && currentExp.company && currentExp.position) {
        experiences.push({
          id: generateId(),
          company: currentExp.company,
          position: currentExp.position,
          startDate: currentExp.startDate || '',
          endDate: currentExp.endDate,
          isCurrent: currentExp.isCurrent,
          achievements: currentExp.achievements || [],
        });
      }

      // Start new experience
      const dates = extractDates(line);
      currentExp = {
        ...dates,
        achievements: [],
      };

      // Try to extract company and position from this line and nearby lines
      const cleanLine = line.replace(/\d{4}|present|current|-|–/gi, '').trim();
      if (i > 0 && !experienceLines[i - 1].match(dateRegex)) {
        currentExp.position = experienceLines[i - 1].trim();
        currentExp.company = cleanLine || (i < experienceLines.length - 1 ? experienceLines[i + 1].trim() : '');
      } else {
        currentExp.company = cleanLine;
        currentExp.position = i < experienceLines.length - 1 ? experienceLines[i + 1].trim() : '';
      }
    } else if (currentExp && line.startsWith('-') || line.startsWith('•')) {
      // This is likely an achievement bullet point
      currentExp.achievements = currentExp.achievements || [];
      currentExp.achievements.push(line.replace(/^[-•]\s*/, ''));
    }
  }

  // Add last experience
  if (currentExp && currentExp.company && currentExp.position) {
    experiences.push({
      id: generateId(),
      company: currentExp.company,
      position: currentExp.position,
      startDate: currentExp.startDate || '',
      endDate: currentExp.endDate,
      isCurrent: currentExp.isCurrent,
      achievements: currentExp.achievements || [],
    });
  }

  return experiences;
}

/**
 * Extract education
 */
function extractEducation(text: string, lines: string[]): Education[] {
  const education: Education[] = [];
  const educationKeywords = ['education', 'academic', 'qualifications'];

  const lowerText = text.toLowerCase();
  let educationStartIndex = -1;

  for (const keyword of educationKeywords) {
    const index = lowerText.indexOf(keyword);
    if (index !== -1) {
      educationStartIndex = index;
      break;
    }
  }

  if (educationStartIndex === -1) {
    return education;
  }

  const afterEducation = text.substring(educationStartIndex);
  const endMatch = afterEducation.match(/\n\n(EXPERIENCE|SKILLS|CERTIFICATIONS|PROJECTS)/i);
  const educationText = endMatch && endMatch.index
    ? afterEducation.substring(0, endMatch.index)
    : afterEducation;

  const educationLines = educationText.split('\n').filter(l => l.trim().length > 0);

  // Simple pattern: institution, degree, dates
  const degreeKeywords = /bachelor|master|phd|doctorate|associate|diploma|certificate|b\.s\.|m\.s\.|b\.a\.|m\.a\./i;
  let currentEdu: Partial<Education> | null = null;

  for (const line of educationLines) {
    if (degreeKeywords.test(line)) {
      if (currentEdu && currentEdu.institution) {
        education.push({
          id: generateId(),
          institution: currentEdu.institution,
          degree: currentEdu.degree || '',
          field: currentEdu.field,
          startDate: currentEdu.startDate,
          endDate: currentEdu.endDate,
        });
      }

      currentEdu = {
        degree: line.trim(),
      };
    } else if (currentEdu && !currentEdu.institution) {
      currentEdu.institution = line.trim();
    }
  }

  if (currentEdu && currentEdu.institution) {
    education.push({
      id: generateId(),
      institution: currentEdu.institution,
      degree: currentEdu.degree || '',
      field: currentEdu.field,
      startDate: currentEdu.startDate,
      endDate: currentEdu.endDate,
    });
  }

  return education;
}

/**
 * Extract skills
 */
function extractSkills(text: string, lines: string[]): Skill[] {
  const skills: Skill[] = [];
  const skillKeywords = ['skills', 'technical skills', 'competencies', 'technologies'];

  const lowerText = text.toLowerCase();
  let skillsStartIndex = -1;

  for (const keyword of skillKeywords) {
    const index = lowerText.indexOf(keyword);
    if (index !== -1) {
      skillsStartIndex = index;
      break;
    }
  }

  if (skillsStartIndex === -1) {
    return skills;
  }

  const afterSkills = text.substring(skillsStartIndex);
  const endMatch = afterSkills.match(/\n\n(EXPERIENCE|EDUCATION|CERTIFICATIONS|PROJECTS)/i);
  const skillsText = endMatch && endMatch.index
    ? afterSkills.substring(0, endMatch.index)
    : afterSkills;

  // Extract individual skills (commonly separated by commas, bullets, or new lines)
  const skillMatches = skillsText
    .replace(/skills|technical skills|competencies|technologies/gi, '')
    .split(/[,\n•\-]/)
    .map(s => s.trim())
    .filter(s => s.length > 0 && s.length < 50);

  for (const skillName of skillMatches) {
    skills.push({
      name: skillName,
    });
  }

  return skills;
}

/**
 * Extract certifications
 */
function extractCertifications(text: string, lines: string[]): Certification[] {
  const certifications: Certification[] = [];
  const certKeywords = ['certifications', 'certificates', 'licenses'];

  const lowerText = text.toLowerCase();
  let certStartIndex = -1;

  for (const keyword of certKeywords) {
    const index = lowerText.indexOf(keyword);
    if (index !== -1) {
      certStartIndex = index;
      break;
    }
  }

  if (certStartIndex === -1) {
    return certifications;
  }

  const afterCert = text.substring(certStartIndex);
  const endMatch = afterCert.match(/\n\n(EXPERIENCE|EDUCATION|SKILLS|PROJECTS)/i);
  const certText = endMatch && endMatch.index
    ? afterCert.substring(0, endMatch.index)
    : afterCert;

  const certLines = certText.split('\n').filter(l => l.trim().length > 0);

  for (const line of certLines) {
    if (line.toLowerCase().includes('certification') || line.toLowerCase().includes('certificate')) {
      continue; // Skip header lines
    }

    certifications.push({
      id: generateId(),
      name: line.trim(),
      issuer: '', // Would need more sophisticated parsing to extract issuer
    });
  }

  return certifications;
}

/**
 * Extract projects
 */
function extractProjects(text: string, lines: string[]): Project[] {
  const projects: Project[] = [];
  const projectKeywords = ['projects', 'portfolio', 'work samples'];

  const lowerText = text.toLowerCase();
  let projectsStartIndex = -1;

  for (const keyword of projectKeywords) {
    const index = lowerText.indexOf(keyword);
    if (index !== -1) {
      projectsStartIndex = index;
      break;
    }
  }

  if (projectsStartIndex === -1) {
    return projects;
  }

  const afterProjects = text.substring(projectsStartIndex);
  const endMatch = afterProjects.match(/\n\n(EXPERIENCE|EDUCATION|SKILLS|CERTIFICATIONS)/i);
  const projectsText = endMatch && endMatch.index
    ? afterProjects.substring(0, endMatch.index)
    : afterProjects;

  const projectLines = projectsText.split('\n').filter(l => l.trim().length > 0);

  let currentProject: Partial<Project> | null = null;

  for (const line of projectLines) {
    if (line.startsWith('-') || line.startsWith('•')) {
      if (currentProject && !currentProject.description) {
        currentProject.description = line.replace(/^[-•]\s*/, '');
      }
    } else if (line.length > 0) {
      if (currentProject && currentProject.name) {
        projects.push({
          id: generateId(),
          name: currentProject.name,
          description: currentProject.description || '',
        });
      }

      currentProject = {
        name: line.trim(),
      };
    }
  }

  if (currentProject && currentProject.name) {
    projects.push({
      id: generateId(),
      name: currentProject.name,
      description: currentProject.description || '',
    });
  }

  return projects;
}

/**
 * Extract languages
 */
function extractLanguages(text: string, lines: string[]): Language[] {
  const languages: Language[] = [];
  const langKeywords = ['languages'];

  const lowerText = text.toLowerCase();
  let langStartIndex = -1;

  for (const keyword of langKeywords) {
    const index = lowerText.indexOf(keyword);
    if (index !== -1) {
      langStartIndex = index;
      break;
    }
  }

  if (langStartIndex === -1) {
    return languages;
  }

  const afterLang = text.substring(langStartIndex);
  const endMatch = afterLang.match(/\n\n/);
  const langText = endMatch && endMatch.index
    ? afterLang.substring(0, endMatch.index)
    : afterLang;

  const langItems = langText
    .replace(/languages/gi, '')
    .split(/[,\n•\-]/)
    .map(s => s.trim())
    .filter(s => s.length > 0);

  for (const item of langItems) {
    const proficiencyMatch = item.match(/(native|fluent|professional|limited|basic)/i);
    const proficiency = proficiencyMatch
      ? proficiencyMatch[0] as Language['proficiency']
      : 'Professional';

    const name = item.replace(/(native|fluent|professional|limited|basic)/gi, '').trim();

    if (name.length > 0) {
      languages.push({
        name,
        proficiency,
      });
    }
  }

  return languages;
}

/**
 * Extract dates from a string
 */
function extractDates(text: string): { startDate?: string; endDate?: string; isCurrent?: boolean } {
  const dateMatch = text.match(/(\d{4}|present|current)/gi);

  if (!dateMatch || dateMatch.length === 0) {
    return {};
  }

  const dates = dateMatch.map(d => d.toLowerCase());
  const isCurrent = dates.some(d => d === 'present' || d === 'current');

  if (dates.length === 1) {
    return {
      startDate: isCurrent ? undefined : dates[0],
      endDate: isCurrent ? 'Present' : undefined,
      isCurrent,
    };
  }

  return {
    startDate: dates[0] === 'present' || dates[0] === 'current' ? dates[1] : dates[0],
    endDate: isCurrent ? 'Present' : dates[dates.length - 1],
    isCurrent,
  };
}

/**
 * Calculate parsing confidence score
 */
function calculateConfidence(data: Omit<ParsedResume, 'id' | 'rawText' | 'metadata'>): number {
  let score = 0;
  const weights = {
    personalInfo: 0.2,
    workExperience: 0.3,
    education: 0.2,
    skills: 0.2,
    other: 0.1,
  };

  // Personal info
  if (data.personalInfo.name && data.personalInfo.name !== 'Unknown') score += weights.personalInfo * 0.5;
  if (data.personalInfo.email) score += weights.personalInfo * 0.3;
  if (data.personalInfo.phone) score += weights.personalInfo * 0.2;

  // Work experience
  if (data.workExperience.length > 0) {
    score += weights.workExperience;
  }

  // Education
  if (data.education.length > 0) {
    score += weights.education;
  }

  // Skills
  if (data.skills.length > 0) {
    score += weights.skills;
  }

  // Other sections
  if (data.certifications.length > 0 || data.projects.length > 0) {
    score += weights.other;
  }

  return Math.min(score, 1);
}

/**
 * Generate a unique ID
 */
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}
