import { test, expect } from '../fixtures/pages';
import { testResume, testJob } from '../fixtures/test-data';

/**
 * Fast Mocked Workflow Integration Test
 *
 * This test runs the complete UI workflow with mocked API responses.
 * It tests UI rendering, state transitions, and data parsing without
 * real LLM or MCP calls, completing in seconds instead of minutes.
 *
 * Mocked endpoints:
 * - POST /api/optimize/start
 * - GET /api/optimize/status/{thread_id}
 * - POST /api/optimize/{thread_id}/answer
 * - POST /api/optimize/{thread_id}/discovery/confirm
 * - GET /api/optimize/{thread_id}/drafting/state
 * - POST /api/optimize/{thread_id}/drafting/approve
 * - POST /api/optimize/{thread_id}/export/start
 * - GET /api/optimize/{thread_id}/export/state
 * - GET /api/optimize/{thread_id}/export/ats-report
 * - GET /api/optimize/{thread_id}/export/linkedin
 */

// Mock data constants
const MOCK_THREAD_ID = 'mock-thread-12345';

const mockUserProfile = {
  name: 'John Doe',
  email: 'john.doe@email.com',
  phone: '(555) 123-4567',
  location: 'San Francisco, CA',
  headline: 'Senior Software Engineer',
  linkedin_url: 'linkedin.com/in/johndoe',
  summary: 'Experienced software engineer with 8+ years of expertise in full-stack development.',
  experience: [
    {
      company: 'TechCorp Inc.',
      position: 'Senior Software Engineer',
      location: 'San Francisco, CA',
      start_date: 'Jan 2020',
      end_date: 'Present',
      highlights: [
        'Led development of microservices architecture serving 10M+ daily users',
        'Implemented CI/CD pipelines reducing deployment time by 70%',
        'Mentored team of 5 junior developers',
      ],
    },
    {
      company: 'StartupXYZ',
      position: 'Software Engineer',
      location: 'Mountain View, CA',
      start_date: 'Jun 2016',
      end_date: 'Dec 2019',
      highlights: [
        'Built real-time data processing pipeline handling 1M events/hour',
        'Developed RESTful APIs using Python/FastAPI',
      ],
    },
  ],
  skills: ['Python', 'TypeScript', 'JavaScript', 'Go', 'React', 'FastAPI', 'AWS', 'Docker'],
  education: [
    {
      institution: 'Stanford University',
      degree: 'B.S. Computer Science',
      year: '2016',
    },
  ],
};

const mockJobPosting = {
  title: 'Senior Software Engineer',
  company_name: 'AI Startup Inc.',
  location: 'Remote',
  url: 'https://example.com/jobs/senior-engineer',
  requirements: [
    '5+ years of software engineering experience',
    'Strong proficiency in Python and TypeScript',
    'Experience with React and modern frontend frameworks',
    'Familiarity with cloud platforms (AWS/GCP)',
    'Experience with microservices architecture',
  ],
  preferred: [
    'Experience with ML/AI systems',
    'Contributions to open source projects',
    'Experience mentoring junior engineers',
  ],
  responsibilities: [
    'Build and maintain scalable backend services',
    'Collaborate with cross-functional teams',
    'Mentor junior team members',
  ],
  benefits: ['Competitive salary ($180K - $250K)', 'Equity compensation', 'Unlimited PTO'],
  tech_stack: ['Python', 'TypeScript', 'React', 'AWS'],
};

const mockGapAnalysis = {
  gaps: [
    'Experience with ML/AI systems - not mentioned in resume',
    'Kubernetes experience - preferred but not listed',
  ],
  strengths: [
    'Python and TypeScript proficiency - 8+ years experience listed',
    'Microservices architecture - led microservices migration at TechCorp',
    'Strong leadership and mentorship experience',
  ],
  transferable_skills: [
    'Backend development with Python/FastAPI',
    'Frontend development with React/TypeScript',
    'Team leadership and mentoring',
    'CI/CD pipeline implementation',
  ],
  opportunities: [
    'Highlight mentorship experience more prominently',
    'Add specific metrics to leadership achievements',
  ],
  keywords_to_include: ['Python', 'TypeScript', 'React', 'AWS', 'microservices', 'ML', 'AI'],
};

const mockResearch = {
  company_culture: 'Fast-paced AI startup with remote-first culture',
  tech_stack: ['Python', 'TypeScript', 'React', 'AWS'],
  similar_hires: ['Engineers from FAANG companies'],
  recent_news: ['Series B funding round'],
};

const mockDiscoveryPrompts = [
  {
    id: 'prompt_1',
    question: 'Can you tell me about a time when you worked with ML/AI systems?',
    category: 'gap_filling',
    priority: 1,
    linked_gap: 'gap_1',
  },
];

const mockDiscoveryMessages = [
  { role: 'assistant', content: 'Can you tell me about a time when you worked with ML/AI systems?' },
  {
    role: 'user',
    content: 'I integrated an ML model for recommendation engine at TechCorp, improving user engagement by 25%.',
  },
  { role: 'assistant', content: 'Great! What technologies did you use for this integration?' },
  { role: 'user', content: 'I used Python with TensorFlow and deployed on AWS SageMaker.' },
  { role: 'assistant', content: 'Excellent experience! Can you tell me about your leadership style when mentoring?' },
  {
    role: 'user',
    content: 'I believe in hands-on mentorship, regular 1:1s, and creating safe spaces for questions.',
  },
];

const mockResumeHtml = `
<div class="resume">
  <h1>John Doe</h1>
  <p>Senior Software Engineer | San Francisco, CA</p>
  <p>john.doe@email.com | (555) 123-4567</p>

  <h2>Summary</h2>
  <p>Results-driven Senior Software Engineer with 8+ years of experience building scalable distributed systems and leading high-performing teams. Expert in Python, TypeScript, React, and cloud-native architectures with a passion for ML/AI integration.</p>

  <h2>Experience</h2>
  <h3>Senior Software Engineer | TechCorp Inc.</h3>
  <p>San Francisco, CA | Jan 2020 - Present</p>
  <ul>
    <li>Led development of microservices architecture serving 10M+ daily users with 99.99% uptime</li>
    <li>Implemented CI/CD pipelines reducing deployment time by 70%</li>
    <li>Integrated ML recommendation engine using TensorFlow and AWS SageMaker, improving user engagement by 25%</li>
    <li>Mentored team of 5 junior developers through structured 1:1s and hands-on code reviews</li>
  </ul>

  <h2>Skills</h2>
  <p>Python, TypeScript, JavaScript, Go, React, FastAPI, TensorFlow, AWS, GCP, Docker, Kubernetes</p>

  <h2>Education</h2>
  <p>B.S. Computer Science | Stanford University | 2016</p>
</div>
`;

const mockAtsReport = {
  keyword_match_score: 85,
  keywords_found: ['Python', 'TypeScript', 'React', 'AWS', 'microservices', 'CI/CD', 'mentoring'],
  keywords_missing: ['Kubernetes', 'GCP'],
  formatting_issues: [],
  recommendations: [
    'Add specific metrics to leadership experience',
    'Include Kubernetes experience if applicable',
  ],
};

const mockLinkedInSuggestions = {
  headline: 'Senior Software Engineer | Python & TypeScript Expert | Building Scalable AI Systems at TechCorp',
  summary:
    'I build scalable systems that serve millions of users. At TechCorp, I lead a team developing microservices architecture and have integrated ML solutions that drive measurable business impact. Passionate about mentoring the next generation of engineers.',
  experience_bullets: [
    'Led microservices migration serving 10M+ daily users with 99.99% uptime',
    'Integrated ML recommendation engine improving engagement by 25%',
    'Mentored 5 junior engineers through structured development programs',
  ],
};

test.describe('Mocked Full Workflow', () => {
  test.setTimeout(60000); // 1 minute timeout (should complete in ~10-20 seconds)

  test.beforeEach(async ({ page }) => {
    // Track current workflow step for status endpoint cycling
    let currentStep = 'ingest';
    let statusCallCount = 0;

    // Mock all API endpoints
    await page.route('**/api/optimize/start', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          thread_id: MOCK_THREAD_ID,
          current_step: 'ingest',
          status: 'running',
          progress: { ingest: 'in_progress' },
        }),
      });
      // After start, immediately transition to research complete
      currentStep = 'research_complete';
    });

    // Status endpoint - cycle through workflow states
    await page.route(`**/api/optimize/status/${MOCK_THREAD_ID}**`, async (route) => {
      statusCallCount++;

      let response: Record<string, unknown>;

      // Simulate workflow progression
      if (currentStep === 'ingest' || statusCallCount <= 2) {
        // First couple calls: still in research
        response = {
          thread_id: MOCK_THREAD_ID,
          current_step: 'research',
          status: 'running',
          progress: { ingest: 'completed', research: 'in_progress' },
          progress_messages: [
            { timestamp: new Date().toISOString(), phase: 'research', message: 'Analyzing profile...', detail: '' },
          ],
        };
      } else if (currentStep === 'research_complete') {
        // Research complete - show results with enough exchanges to enable confirm
        response = {
          thread_id: MOCK_THREAD_ID,
          current_step: 'discovery',
          status: 'waiting_input',
          progress: { ingest: 'completed', research: 'completed', discovery: 'in_progress' },
          user_profile: mockUserProfile,
          job_posting: mockJobPosting,
          research: mockResearch,
          gap_analysis: mockGapAnalysis,
          discovery_prompts: mockDiscoveryPrompts,
          discovery_messages: mockDiscoveryMessages, // All messages (3 exchanges)
          discovery_exchanges: 3, // 3 exchanges = confirm button enabled
          discovery_confirmed: false,
          interrupt_payload: {
            message: 'Any other experiences to share?',
            interrupt_type: 'discovery',
          },
        };
      } else if (currentStep === 'discovery') {
        response = {
          thread_id: MOCK_THREAD_ID,
          current_step: 'discovery',
          status: 'waiting_input',
          progress: { ingest: 'completed', research: 'completed', discovery: 'in_progress' },
          user_profile: mockUserProfile,
          job_posting: mockJobPosting,
          gap_analysis: mockGapAnalysis,
          discovery_prompts: mockDiscoveryPrompts,
          discovery_messages: mockDiscoveryMessages,
          discovery_exchanges: 3,
          interrupt_payload: {
            message: 'Do you have any other experiences to share?',
            interrupt_type: 'discovery',
          },
        };
      } else if (currentStep === 'drafting' || currentStep === 'editor') {
        response = {
          thread_id: MOCK_THREAD_ID,
          current_step: 'editor',
          status: 'waiting_input',
          progress: {
            ingest: 'completed',
            research: 'completed',
            discovery: 'completed',
            draft: 'completed',
            editor: 'in_progress',
          },
          user_profile: mockUserProfile,
          job_posting: mockJobPosting,
          gap_analysis: mockGapAnalysis,
          resume_html: mockResumeHtml,
          discovery_confirmed: true, // Required for stepper to unlock drafting
          draft_approved: false,
        };
      } else if (currentStep === 'export') {
        response = {
          thread_id: MOCK_THREAD_ID,
          current_step: 'completed',
          status: 'completed',
          progress: {
            ingest: 'completed',
            research: 'completed',
            discovery: 'completed',
            draft: 'completed',
            editor: 'completed',
            export: 'completed',
          },
          user_profile: mockUserProfile,
          job_posting: mockJobPosting,
          resume_html: mockResumeHtml,
          discovery_confirmed: true,  // Required for stepper
          draft_approved: true,       // Required for stepper to unlock export
          export_completed: true,
          ats_report: mockAtsReport,
          linkedin_suggestions: mockLinkedInSuggestions,
        };
      } else {
        response = {
          thread_id: MOCK_THREAD_ID,
          current_step: currentStep,
          status: 'running',
          progress: {},
        };
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(response),
      });
    });

    // Answer endpoint - transitions workflow based on current step
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/answer`, async (route) => {
      // If we're in drafting and get an answer (approve), transition to export
      if (currentStep === 'drafting' || currentStep === 'editor') {
        currentStep = 'export';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            thread_id: MOCK_THREAD_ID,
            current_step: 'completed',
            status: 'completed',
            discovery_confirmed: true,
            draft_approved: true,
          }),
        });
      } else {
        // Discovery answer
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            thread_id: MOCK_THREAD_ID,
            current_step: 'discovery',
            status: 'waiting_input',
            discovery_exchanges: 3,
            discovery_messages: mockDiscoveryMessages,
          }),
        });
      }
    });

    // Discovery confirm endpoint
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/discovery/confirm`, async (route) => {
      currentStep = 'drafting';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          thread_id: MOCK_THREAD_ID,
          current_step: 'editor',
          status: 'waiting_input',
        }),
      });
    });

    // Drafting state endpoint
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/drafting/state`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          thread_id: MOCK_THREAD_ID,
          resume_html: mockResumeHtml,
          suggestions: [],
          versions: [
            {
              version: '1.0',
              html_content: mockResumeHtml,
              trigger: 'initial',
              description: 'Initial draft',
              created_at: new Date().toISOString(),
            },
          ],
          current_version: '1.0',
          change_log: [],
          draft_approved: false,
          validation: {
            valid: true,
            errors: [],
            warnings: [],
          },
        }),
      });
    });

    // Drafting approve endpoint
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/drafting/approve`, async (route) => {
      currentStep = 'export';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          draft_approved: true,
          validation: { valid: true, errors: [], warnings: [] },
        }),
      });
    });

    // Export start endpoint
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/export/start`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          export_step: 'completed',
          ats_report: mockAtsReport,
          linkedin_suggestions: mockLinkedInSuggestions,
        }),
      });
    });

    // Export state endpoint
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/export/state`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          thread_id: MOCK_THREAD_ID,
          export_step: 'completed',
          export_completed: true,
          ats_report: mockAtsReport,
          linkedin_suggestions: mockLinkedInSuggestions,
          draft_approved: true,
        }),
      });
    });

    // ATS report endpoint
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/export/ats-report`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAtsReport),
      });
    });

    // LinkedIn suggestions endpoint
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/export/linkedin`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockLinkedInSuggestions),
      });
    });

    // Download endpoints - return mock files
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/export/download/*`, async (route) => {
      const url = route.request().url();
      const format = url.split('/').pop();

      let contentType = 'application/octet-stream';
      let filename = `john_doe_optimized.${format}`;

      if (format === 'pdf') {
        contentType = 'application/pdf';
      } else if (format === 'txt') {
        contentType = 'text/plain';
      } else if (format === 'json') {
        contentType = 'application/json';
      } else if (format === 'docx') {
        contentType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      }

      await route.fulfill({
        status: 200,
        contentType,
        headers: {
          'Content-Disposition': `attachment; filename="${filename}"`,
        },
        body: Buffer.from('Mock file content'),
      });
    });

    // Data endpoint
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/data`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          thread_id: MOCK_THREAD_ID,
          current_step: currentStep,
          user_profile: mockUserProfile,
          job_posting: mockJobPosting,
          research: mockResearch,
          gap_analysis: mockGapAnalysis,
          resume_html: mockResumeHtml,
        }),
      });
    });

    // Editor update endpoint
    await page.route(`**/api/optimize/${MOCK_THREAD_ID}/editor/update`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, message: 'Resume updated' }),
      });
    });
  });

  test('completes full workflow with mocked API responses', async ({
    landingPage,
    researchPage,
    discoveryPage,
    draftingPage,
    exportPage,
    page,
  }) => {
    // Step 1: Landing Page - Enter resume and job
    console.log('Step 1: Entering resume and job details...');
    await landingPage.goto();
    await landingPage.expectHeroVisible();
    await landingPage.fillResumeText(testResume.text);
    await landingPage.fillJobText(testJob.text);
    await landingPage.startOptimization();
    await landingPage.expectNavigatedToOptimize();

    // Step 2: Research - Wait for mocked research to "complete"
    console.log('Step 2: Verifying research results...');
    await page.waitForTimeout(1000); // Allow state to update
    await researchPage.waitForResearchComplete(10000);
    await researchPage.expectResearchResultsVisible();

    // Verify research data is displayed correctly
    await expect(page.getByText('John Doe').first()).toBeVisible();
    await expect(page.getByText('AI Startup Inc.').first()).toBeVisible();

    await researchPage.continueToDiscovery();

    // Step 3: Discovery - Confirm (mocked with 3 exchanges already)
    console.log('Step 3: Completing discovery...');
    await page.waitForTimeout(1000);
    // Don't wait for chat input - it may be in loading state. Just click confirm button directly.
    await discoveryPage.confirmDiscovery();

    // Step 4: Drafting - Verify editor loads and approve
    console.log('Step 4: Verifying draft editor...');
    await draftingPage.waitForEditor(10000);
    await draftingPage.expectEditorVisible();

    // Verify resume content is displayed
    const editorContent = await draftingPage.getEditorContent();
    expect(editorContent).toContain('John Doe');
    expect(editorContent).toContain('Senior Software Engineer');

    // Type something to verify editor is interactive
    await draftingPage.typeInEditor(' [TEST EDIT]');
    await draftingPage.verifyChangesSaved('[TEST EDIT]');

    await draftingPage.approve();

    // Wait for workflow to transition to export/completed state
    await page.waitForTimeout(2000);

    // Step 5: Export - Verify results
    console.log('Step 5: Verifying export results...');
    // Wait for either export completion or download links
    await exportPage.waitForExportComplete(15000);
    await exportPage.expectExportResultsVisible();
    await exportPage.expectATSReportVisible();
    await exportPage.expectLinkedInVisible();

    // Verify download links are present
    await expect(exportPage.downloadPdfButton).toBeVisible();
    await expect(exportPage.downloadTxtButton).toBeVisible();

    console.log('Mocked workflow completed successfully!');
  });

  test('handles research data parsing correctly', async ({ landingPage, researchPage, page }) => {
    // Focus on data parsing in research step
    await landingPage.goto();
    await landingPage.fillResumeText(testResume.text);
    await landingPage.fillJobText(testJob.text);
    await landingPage.startOptimization();

    await researchPage.waitForResearchComplete(10000);

    // Verify profile data parsing
    await expect(page.getByText('John Doe').first()).toBeVisible();

    // Verify job data parsing
    await expect(page.getByText('AI Startup Inc.').first()).toBeVisible();

    // Verify gap analysis data parsing - look for strength text
    await expect(page.getByText(/Python and TypeScript/i).first()).toBeVisible();
  });

  test('handles discovery UI flow correctly', async ({
    landingPage,
    researchPage,
    discoveryPage,
    page,
  }) => {
    await landingPage.goto();
    await landingPage.fillResumeText(testResume.text);
    await landingPage.fillJobText(testJob.text);
    await landingPage.startOptimization();

    await researchPage.waitForResearchComplete(10000);
    await researchPage.continueToDiscovery();

    // Wait for discovery UI to load
    await page.waitForTimeout(1000);

    // Verify discovery conversation is visible (messages or header)
    await expect(page.getByText('Discovery Conversation')).toBeVisible();

    // Verify the confirm button is available since mock has 3 exchanges
    await expect(discoveryPage.confirmButton).toBeVisible();
  });

  test('handles drafting editor interactions correctly', async ({
    landingPage,
    researchPage,
    discoveryPage,
    draftingPage,
    page,
  }) => {
    await landingPage.goto();
    await landingPage.fillResumeText(testResume.text);
    await landingPage.fillJobText(testJob.text);
    await landingPage.startOptimization();

    await researchPage.waitForResearchComplete(10000);
    await researchPage.continueToDiscovery();

    // Skip waiting for question - mock has 3 exchanges so confirm is ready
    await page.waitForTimeout(1000);
    await discoveryPage.confirmDiscovery();

    await draftingPage.waitForEditor(10000);

    // Verify editor is editable
    await draftingPage.expectEditorVisible();

    // Test text editing
    await draftingPage.typeInEditor(' EDITED');
    const content = await draftingPage.getEditorContent();
    expect(content).toContain('EDITED');

    // Verify approve button is present
    await expect(draftingPage.approveButton).toBeVisible();
  });

  test('handles export data display correctly', async ({
    landingPage,
    researchPage,
    discoveryPage,
    draftingPage,
    exportPage,
    page,
  }) => {
    await landingPage.goto();
    await landingPage.fillResumeText(testResume.text);
    await landingPage.fillJobText(testJob.text);
    await landingPage.startOptimization();

    await researchPage.waitForResearchComplete(10000);
    await researchPage.continueToDiscovery();

    // Skip waiting for question - mock has 3 exchanges
    await page.waitForTimeout(1000);
    await discoveryPage.confirmDiscovery();

    await draftingPage.waitForEditor(10000);
    await draftingPage.approve();
    await page.waitForTimeout(2000);

    await exportPage.waitForExportComplete(15000);

    // Verify ATS report display
    await exportPage.expectATSReportVisible();

    // Verify LinkedIn suggestions display
    await exportPage.expectLinkedInVisible();

    // Verify download format is available
    await expect(exportPage.downloadPdfButton).toBeVisible();
  });
});

test.describe('Mocked UI Edge Cases', () => {
  test.setTimeout(30000);

  test('handles API error gracefully', async ({ landingPage, page }) => {
    // Mock start to return error
    await page.route('**/api/optimize/start', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid resume format' }),
      });
    });

    await landingPage.goto();
    await landingPage.fillResumeText(testResume.text);
    await landingPage.fillJobText(testJob.text);
    await landingPage.startOptimization();

    // Wait for navigation and response
    await page.waitForTimeout(2000);

    // Should show "No Active Workflow" or error message - graceful failure
    const noWorkflow = await page.getByText('No Active Workflow').isVisible().catch(() => false);
    const hasError = await page.getByText(/error|invalid|failed/i).first().isVisible().catch(() => false);
    const onLanding = !page.url().includes('/optimize');

    // Any graceful handling is acceptable
    expect(noWorkflow || hasError || onLanding).toBeTruthy();
  });

  test('handles special characters in profile name', async ({
    landingPage,
    researchPage,
    page,
  }) => {
    const specialProfile = {
      ...mockUserProfile,
      name: 'José García',
      headline: 'Senior Engineer',
    };

    await page.route('**/api/optimize/start', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          thread_id: 'special-chars-thread',
          current_step: 'research',
          status: 'running',
        }),
      });
    });

    await page.route('**/api/optimize/status/special-chars-thread**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          thread_id: 'special-chars-thread',
          current_step: 'discovery',
          status: 'waiting_input',
          user_profile: specialProfile,
          job_posting: mockJobPosting,
          gap_analysis: mockGapAnalysis,
          discovery_messages: mockDiscoveryMessages,
          discovery_exchanges: 3,
          discovery_confirmed: false,
        }),
      });
    });

    await landingPage.goto();
    await landingPage.fillResumeText(testResume.text);
    await landingPage.fillJobText(testJob.text);
    await landingPage.startOptimization();

    await researchPage.waitForResearchComplete(10000);

    // Should display accented characters correctly
    await expect(page.getByText('José García').first()).toBeVisible();
  });
});
