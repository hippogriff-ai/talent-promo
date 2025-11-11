/**
 * Resume Text Parser
 * Converts raw text into structured resume data
 */

import type { ParsedResume, PersonalInfo, WorkExperience, Education, Skill, Certification, Project, Language } from '@/app/types/resume';

const PARSE_VERSION = '1.0.0';

/**
 * Main function to parse resume text into structured data
 */
export function parseResumeText(
  rawText: string,
  fileName: string,
  fileSize: number,
  fileType: string
): ParsedResume {
  if (!rawText || rawText.trim().length === 0) {
    throw new Error('No text content provided');
  }

  // Parse the text into structured data
  const parsedData = parseText(rawText);

  return {
    id: generateId(),
    ...parsedData,
    rawText,
    metadata: {
      fileName,
      fileSize,
      fileType,
      parsedDate: new Date().toISOString(),
      parseVersion: PARSE_VERSION,
      confidence: calculateConfidence(parsedData),
    },
  };
}

/**
 * Parse raw text into structured resume data
 */
function parseText(text: string): Omit<ParsedResume, 'id' | 'rawText' | 'metadata'> {
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
 * Extract work experience with improved hierarchy detection
 */
function extractWorkExperience(text: string, lines: string[]): WorkExperience[] {
  const experiences: WorkExperience[] = [];
  const experienceKeywords = ['professional experience', 'work experience', 'experience', 'work history', 'employment'];

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

  // Extract experience section text - look for next major section
  const afterExperience = text.substring(experienceStartIndex);
  const endMatch = afterExperience.match(/\n(Education|Educations|Skills|Certifications|Projects|Side Projects|Languages|Production Languages)\n/i);
  const experienceText = endMatch && endMatch.index
    ? afterExperience.substring(0, endMatch.index)
    : afterExperience;

  // Parse with line-by-line analysis
  const rawLines = experienceText.split('\n');
  const structuredLines = rawLines.map(line => ({
    original: line,
    indent: line.length - line.trimStart().length,
    trimmed: line.trim(),
  })).filter(l => l.trimmed.length > 0);

  // Skip header line
  let i = 0;
  while (i < structuredLines.length &&
         experienceKeywords.some(kw => structuredLines[i].trimmed.toLowerCase().includes(kw))) {
    i++;
  }

  let currentExp: Partial<WorkExperience> | null = null;
  const dateRangeRegex = /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{1,2}\/)?[\s-]*\d{4}\s*[–—-]\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{1,2}\/)?\s*(\d{4}|Present|Current)/i;
  const bulletRegex = /^[•●○■□▪▫]\s+/;

  while (i < structuredLines.length) {
    const line = structuredLines[i];
    const isBullet = bulletRegex.test(line.trimmed);

    // Check if this line has a date range (indicates job title line)
    const dateRangeMatch = line.trimmed.match(dateRangeRegex);

    if (dateRangeMatch && !isBullet) {
      // Save previous experience
      if (currentExp && currentExp.position) {
        experiences.push({
          id: generateId(),
          company: currentExp.company || '',
          position: currentExp.position,
          startDate: currentExp.startDate || '',
          endDate: currentExp.endDate,
          isCurrent: currentExp.isCurrent,
          achievements: currentExp.achievements || [],
        });
      }

      // Start new experience
      // Extract dates
      const dates = extractDates(dateRangeMatch[0]);

      // Position is everything before the date range
      const positionText = line.trimmed.substring(0, dateRangeMatch.index).trim();

      // Company is usually the next line
      let company = '';
      if (i + 1 < structuredLines.length && !bulletRegex.test(structuredLines[i + 1].trimmed)) {
        company = structuredLines[i + 1].trimmed;
        // Check if company line also doesn't have dates (to avoid catching another position)
        if (!dateRangeRegex.test(company)) {
          i++; // Skip the company line
        } else {
          company = ''; // This was actually another position
        }
      }

      currentExp = {
        position: positionText,
        company,
        startDate: dates.startDate || '',
        endDate: dates.endDate,
        isCurrent: dates.isCurrent,
        achievements: [],
      };
    } else if (currentExp && isBullet) {
      // This is an achievement bullet
      const achievement = line.trimmed.replace(bulletRegex, '').trim();
      if (achievement.length > 0) {
        currentExp.achievements = currentExp.achievements || [];

        // Check for sub-bullets on following lines
        let fullAchievement = achievement;
        let j = i + 1;
        while (j < structuredLines.length &&
               structuredLines[j].indent > line.indent &&
               bulletRegex.test(structuredLines[j].trimmed)) {
          const subBullet = structuredLines[j].trimmed.replace(bulletRegex, '').trim();
          fullAchievement += '\n  ' + subBullet;
          j++;
        }

        currentExp.achievements.push(fullAchievement);
        i = j - 1; // Skip the sub-bullets we just processed
      }
    }

    i++;
  }

  // Add last experience
  if (currentExp && currentExp.position) {
    experiences.push({
      id: generateId(),
      company: currentExp.company || '',
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
 * Check if a line looks like a company name
 */
function isLikelyCompany(text: string): boolean {
  const companyIndicators = ['Inc', 'LLC', 'Corp', 'Ltd', 'Company', 'Technologies', 'Systems', 'Solutions', 'Services'];
  return companyIndicators.some(indicator => text.includes(indicator));
}

/**
 * Check if a line looks like a company name or job title
 */
function isLikelyCompanyOrTitle(text: string): boolean {
  // Check length - company names and titles are usually substantial
  if (text.length < 3 || text.length > 100) return false;

  // Check for company indicators
  if (isLikelyCompany(text)) return true;

  // Check for title indicators
  const titleWords = ['Engineer', 'Developer', 'Manager', 'Director', 'Analyst', 'Designer', 'Lead', 'Senior', 'Junior', 'Specialist', 'Consultant', 'Coordinator', 'Administrator'];
  if (titleWords.some(word => text.includes(word))) return true;

  // Check if it's mostly alphabetic (company/title vs random symbols)
  const alphaRatio = (text.match(/[a-zA-Z]/g) || []).length / text.length;
  return alphaRatio > 0.6;
}

/**
 * Extract education
 */
function extractEducation(text: string, lines: string[]): Education[] {
  const education: Education[] = [];
  const educationKeywords = ['education', 'educations', 'academic', 'qualifications'];

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
  const endMatch = afterEducation.match(/\n(Professional Experience|Experience|Skills|Certifications|Projects|Side Projects|Production Languages)\n/i);
  const educationText = endMatch && endMatch.index
    ? afterEducation.substring(0, endMatch.index)
    : afterEducation;

  const educationLines = educationText.split('\n').map(l => l.trim()).filter(l => l.length > 0);

  // Skip header
  let i = 0;
  while (i < educationLines.length && educationKeywords.some(kw => educationLines[i].toLowerCase().includes(kw))) {
    i++;
  }

  const dateRegex = /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\\d{1,2}\/)?\s*\d{4}/i;
  const degreeKeywords = /bachelor|master|m\.s\.|b\.s\.|m\.a\.|b\.a\.|phd|doctorate|associate|diploma/i;

  while (i < educationLines.length) {
    const line = educationLines[i];

    // Check if line has university/institution name (usually has a comma and date at end)
    const hasDate = dateRegex.test(line);

    if (hasDate && !line.startsWith('●') && !line.startsWith('○')) {
      // Extract institution, degree, and date
      const dateMatch = line.match(dateRegex);
      let endDate = '';
      let institutionAndDegree = line;

      if (dateMatch) {
        endDate = dateMatch[0];
        institutionAndDegree = line.substring(0, dateMatch.index).trim();
      }

      // Check if degree is in the same line (format: "University, Degree, Field, Location")
      const parts = institutionAndDegree.split(',').map(p => p.trim());

      let institution = '';
      let degree = '';
      let field = '';

      if (parts.length >= 2) {
        institution = parts[0];
        // Check which part contains degree keywords
        for (let j = 1; j < parts.length; j++) {
          if (degreeKeywords.test(parts[j])) {
            degree = parts[j];
            if (j + 1 < parts.length && !parts[j + 1].toLowerCase().includes('usa') && !parts[j + 1].toLowerCase().includes('new york')) {
              field = parts[j + 1];
            }
            break;
          }
        }
      } else {
        institution = institutionAndDegree;
      }

      if (institution) {
        education.push({
          id: generateId(),
          institution,
          degree,
          field,
          endDate,
        });
      }
    }

    i++;
  }

  return education;
}

/**
 * Extract skills with improved parsing
 */
function extractSkills(text: string, lines: string[]): Skill[] {
  const skills: Skill[] = [];
  const skillKeywords = ['production languages', 'programming languages', 'skills', 'technical skills', 'competencies', 'technologies', 'tools'];

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
  // Look for end of section - usually end of document or next major heading
  const endMatch = afterSkills.match(/\n\n\n|$$/);
  const skillsText = endMatch && endMatch.index
    ? afterSkills.substring(0, endMatch.index)
    : afterSkills;

  // Remove header keywords
  const cleanedText = skillsText.replace(/production languages|programming languages|skills|technical skills|competencies|technologies|tools/gi, '');

  // Extract individual skills (commonly separated by commas, bullets, pipes, or new lines)
  const bulletRegex = /^[•●○■□▪▫–—-]\s*/;
  const skillMatches = cleanedText
    .split(/[,\n|]/)
    .map(s => s.trim().replace(bulletRegex, '').trim())
    .filter(s => {
      // Filter out empty, too short, or too long entries
      if (s.length < 2 || s.length > 50) return false;
      // Filter out common non-skill words
      const nonSkills = ['and', 'or', 'with', 'using', 'including', 'such as'];
      if (nonSkills.includes(s.toLowerCase())) return false;
      // Ensure it has some alphabetic characters
      return /[a-zA-Z]/.test(s);
    });

  // Deduplicate skills
  const uniqueSkills = new Set<string>();
  for (const skillName of skillMatches) {
    const normalized = skillName.trim();
    if (normalized && !uniqueSkills.has(normalized.toLowerCase())) {
      uniqueSkills.add(normalized.toLowerCase());
      skills.push({
        name: normalized,
      });
    }
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
 * Extract projects - handles both course projects and side projects
 */
function extractProjects(text: string, lines: string[]): Project[] {
  const projects: Project[] = [];

  // Look for course projects (CS### pattern) within Education section or elsewhere
  const courseProjectRegex = /(CS\d+[A-Z]*)\s+([^\n]+?)(?:\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|\s+\d{4})?(?=\n)/gi;
  let match;

  while ((match = courseProjectRegex.exec(text)) !== null) {
    const courseCode = match[1];
    const courseName = match[2].trim();
    const projectName = `${courseCode} ${courseName}`;

    // Find project details after this course name
    const afterCourse = text.substring(match.index + match[0].length);
    const projectMatch = afterCourse.match(/●\s*Project:\s*([^\n]+)/i);

    if (projectMatch && projectMatch.index !== undefined) {
      const projectTitle = projectMatch[1].trim();

      // Extract description bullets after the project title
      const afterProjectTitle = afterCourse.substring(projectMatch.index + projectMatch[0].length);
      const descriptionBullets: string[] = [];
      const bulletLines = afterProjectTitle.split('\n');

      for (const line of bulletLines) {
        const trimmedLine = line.trim();
        if (trimmedLine.startsWith('○')) {
          descriptionBullets.push(trimmedLine.replace(/^○\s*/, ''));
        } else if (trimmedLine.startsWith('●') || trimmedLine.match(/^(CS\d+|Side Projects|Production Languages|Education)/i)) {
          // Hit another section or course
          break;
        } else if (descriptionBullets.length > 0 && trimmedLine.length > 0 && !trimmedLine.startsWith('Presentation link')) {
          // Continuation of previous bullet
          descriptionBullets[descriptionBullets.length - 1] += ' ' + trimmedLine;
        }
      }

      projects.push({
        id: generateId(),
        name: projectTitle,
        description: descriptionBullets.join('\n'),
      });
    }
  }

  // Look for "Side Projects" section
  const sideProjectsMatch = text.match(/Side Projects\s*\n([\s\S]+?)(?=\n(?:Production Languages|Skills|Education|$))/i);

  if (sideProjectsMatch) {
    const sideProjectsText = sideProjectsMatch[1];
    const lines = sideProjectsText.split('\n').map(l => l.trim()).filter(l => l.length > 0);

    let currentSideProject: Partial<Project> | null = null;

    for (const line of lines) {
      if (line.startsWith('●')) {
        // Save previous project
        if (currentSideProject && currentSideProject.name) {
          projects.push({
            id: generateId(),
            name: currentSideProject.name,
            description: currentSideProject.description || '',
          });
        }

        // Start new project
        const projectName = line.replace(/^●\s*/, '').trim();
        currentSideProject = {
          name: projectName,
          description: '',
        };
      } else if (currentSideProject && line.startsWith('○')) {
        // Description bullet
        const bullet = line.replace(/^○\s*/, '').trim();
        if (currentSideProject.description) {
          currentSideProject.description += '\n' + bullet;
        } else {
          currentSideProject.description = bullet;
        }
      }
    }

    // Add last side project
    if (currentSideProject && currentSideProject.name) {
      projects.push({
        id: generateId(),
        name: currentSideProject.name,
        description: currentSideProject.description || '',
      });
    }
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
