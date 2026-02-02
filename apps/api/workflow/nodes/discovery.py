"""Discovery node for surfacing hidden/forgotten experiences.

This node handles:
1. Generating discovery prompts based on gap analysis
2. Processing user responses to extract experiences
3. Managing the discovery conversation flow
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from anthropic import Anthropic

from workflow.state import (
    ResumeState,
    DiscoveryPrompt,
    DiscoveredExperience,
    DiscoveryMessage,
    GapAnalysis,
    AgendaTopic,
    DiscoveryAgenda,
)
from config import get_settings
from workflow.nodes.ingest import estimate_seniority

logger = logging.getLogger(__name__)


def _extract_json_from_response(content: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks.

    Handles responses wrapped in ```json or ``` code fences.
    """
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    return json.loads(content.strip())


def get_anthropic_client() -> Anthropic:
    """Get configured Anthropic client."""
    settings = get_settings()
    return Anthropic(api_key=settings.anthropic_api_key)


async def generate_discovery_agenda(state: ResumeState) -> dict:
    """Generate a structured discovery agenda based on gap analysis.

    Creates 5-6 high-level topics that cluster related gaps together.
    Each topic becomes a focal point for 1-2 targeted questions.

    Returns:
        Serialized DiscoveryAgenda dict
    """
    gap_analysis = state.get("gap_analysis", {})
    profile_text = state.get("profile_text") or state.get("profile_markdown") or ""
    job_text = state.get("job_text") or state.get("job_markdown") or ""

    if not gap_analysis:
        logger.warning("No gap analysis found, cannot generate discovery agenda")
        return DiscoveryAgenda().model_dump()

    gaps = gap_analysis.get("gaps", [])
    gaps_detailed = gap_analysis.get("gaps_detailed", [])
    opportunities = gap_analysis.get("opportunities", [])
    strengths = gap_analysis.get("strengths", [])

    # Get job info
    job_posting = state.get("job_posting", {})
    job_title = state.get("job_title") or job_posting.get("title", "the target role")
    company_name = state.get("job_company") or job_posting.get("company_name", "the company")
    requirements = job_posting.get("requirements", [])

    # Get user info
    user_profile = state.get("user_profile", {})
    user_name = state.get("profile_name") or user_profile.get("name", "the candidate")

    prompt = f"""You are designing a discovery conversation for {user_name} applying to {job_title} at {company_name}.

## YOUR TASK
Cluster the gaps and opportunities into 5-6 distinct TOPICS for discovery.

Topics should be:
- High-level themes (not specific questions)
- Mutually exclusive (don't repeat the same angle)
- Ordered by importance to this specific job
- Framed positively (finding hidden value, not filling deficits)

## GAPS TO ADDRESS
{chr(10).join(f"- {g}" for g in gaps[:8])}

## OPPORTUNITIES TO EXPLORE
{chr(10).join(f"- {o.get('description', o) if isinstance(o, dict) else o}" for o in opportunities[:5]) if opportunities else "See gaps above"}

## STRENGTHS TO BUILD ON
{chr(10).join(f"- {s}" for s in strengths[:5]) if strengths else "See profile below"}

## JOB REQUIREMENTS
{chr(10).join(f"- {r}" for r in requirements[:6]) if requirements else "See job description"}

## PROFILE CONTEXT (abbreviated)
{profile_text[:2000] if profile_text else "No profile available"}

## OUTPUT FORMAT
Return JSON array with 5-6 topics:
[
  {{
    "title": "Short title (2-4 words)",
    "goal": "What we want to discover - one sentence",
    "related_gaps": ["Gap 1", "Gap 2"],
    "priority": 1
  }}
]

GOOD titles: "Leadership Impact", "Technical Problem-Solving", "Cross-Team Collaboration", "Hidden Quantifiable Wins"
BAD titles: "Tell me about leadership" (too vague), "Kubernetes experience gap" (too specific/deficit-focused)
"""

    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        topics_data = _extract_json_from_response(content)

        # Convert to AgendaTopic objects
        topics = []
        for i, t in enumerate(topics_data[:6]):  # Max 6 topics
            topic = AgendaTopic(
                id=f"topic_{uuid.uuid4().hex[:8]}",
                title=t.get("title", f"Topic {i+1}"),
                goal=t.get("goal", ""),
                related_gaps=t.get("related_gaps", []),
                priority=t.get("priority", i + 1),
                status="pending",
                prompts_asked=0,
                max_prompts=2,
                experiences_found=[],
            )
            topics.append(topic)

        # Create agenda
        agenda = DiscoveryAgenda(
            topics=[t.model_dump() for t in topics],
            current_topic_id=topics[0].id if topics else None,
            total_topics=len(topics),
            covered_topics=0,
        )

        # Set first topic to in_progress
        if agenda.topics:
            agenda.topics[0]["status"] = "in_progress"

        logger.info(f"Generated discovery agenda with {len(topics)} topics")
        return agenda.model_dump()

    except Exception as e:
        logger.error(f"Failed to generate discovery agenda: {e}")
        # Return default agenda with fallback topics
        return _get_fallback_agenda(gaps)


def _get_fallback_agenda(gaps: list[str]) -> dict:
    """Generate a fallback agenda if LLM fails."""
    fallback_topics = [
        {"title": "Leadership & Initiative", "goal": "Surface times you led without formal authority", "priority": 1},
        {"title": "Technical Problem-Solving", "goal": "Find complex challenges you solved creatively", "priority": 2},
        {"title": "Cross-Team Impact", "goal": "Discover influence beyond your immediate team", "priority": 3},
        {"title": "Hidden Quantifiable Wins", "goal": "Uncover metrics you might have downplayed", "priority": 4},
        {"title": "Transferable Skills", "goal": "Bridge non-traditional experience to job requirements", "priority": 5},
    ]

    topics = []
    for i, t in enumerate(fallback_topics):
        topic = AgendaTopic(
            id=f"topic_{uuid.uuid4().hex[:8]}",
            title=t["title"],
            goal=t["goal"],
            related_gaps=gaps[i:i+2] if i < len(gaps) else [],
            priority=t["priority"],
            status="pending" if i > 0 else "in_progress",
            prompts_asked=0,
            max_prompts=2,
            experiences_found=[],
        )
        topics.append(topic.model_dump())

    return DiscoveryAgenda(
        topics=topics,
        current_topic_id=topics[0]["id"] if topics else None,
        total_topics=len(topics),
        covered_topics=0,
    ).model_dump()


async def generate_topic_prompts(state: ResumeState, topic: dict) -> list[dict]:
    """Generate 1-2 prompts for a specific agenda topic.

    This is called per-topic instead of generating all prompts upfront,
    allowing more context-aware questioning based on conversation history.
    """
    gap_analysis = state.get("gap_analysis", {})
    profile_text = state.get("profile_text") or state.get("profile_markdown") or ""
    job_posting = state.get("job_posting", {})
    discovery_messages = state.get("discovery_messages", [])

    # Get job info
    job_title = state.get("job_title") or job_posting.get("title", "the target role")
    company_name = state.get("job_company") or job_posting.get("company_name", "the company")
    requirements = job_posting.get("requirements", [])

    # Get user info
    user_profile = state.get("user_profile", {})
    user_name = state.get("profile_name") or user_profile.get("name", "the candidate")

    # Build conversation context
    recent_messages = discovery_messages[-6:] if discovery_messages else []
    conversation_context = ""
    if recent_messages:
        conversation_context = "## RECENT CONVERSATION\n"
        for msg in recent_messages:
            role = "AI" if msg.get("role") == "agent" else "User"
            conversation_context += f"{role}: {msg.get('content', '')[:200]}...\n"

    # Estimate seniority
    seniority = estimate_seniority(profile_text)

    prompt = f"""You are a career coach helping {user_name} prepare for {job_title} at {company_name}.

## CURRENT TOPIC: {topic.get('title', 'Discovery')}
Goal: {topic.get('goal', 'Surface hidden experiences')}
Related gaps to address: {', '.join(topic.get('related_gaps', [])[:3])}

## SENIORITY LEVEL: {seniority.upper()}

{conversation_context}

## PROFILE CONTEXT
{profile_text[:2500] if profile_text else "No profile available"}

## YOUR TASK
Generate 1-2 TARGETED questions for this specific topic.

RULES:
- Questions must be SHORT (max 20 words)
- Reference SPECIFIC companies/achievements from their profile
- Frame positively (find hidden value, don't highlight deficits)
- Include escape hatches for pivoting if topic doesn't resonate
- Don't repeat topics already covered in the conversation

## OUTPUT FORMAT
[
  {{
    "question": "Your short, specific question here",
    "intent": "What hidden value this surfaces"
  }}
]
"""

    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        prompts_data = _extract_json_from_response(content)

        prompts = []
        for p in prompts_data[:2]:  # Max 2 prompts per topic
            prompt_obj = DiscoveryPrompt(
                id=str(uuid.uuid4()),
                question=p.get("question", ""),
                intent=p.get("intent", ""),
                related_gaps=topic.get("related_gaps", []),
                priority=1,
                asked=False,
                topic_id=topic.get("id"),
                is_follow_up=False,
            )
            prompts.append(prompt_obj.model_dump())

        logger.info(f"Generated {len(prompts)} prompts for topic '{topic.get('title')}'")
        return prompts

    except Exception as e:
        logger.error(f"Failed to generate topic prompts: {e}")
        # Return a single fallback prompt
        return [{
            "id": str(uuid.uuid4()),
            "question": f"Tell me about a time when you {topic.get('goal', 'demonstrated hidden value').lower()}",
            "intent": topic.get("goal", ""),
            "related_gaps": topic.get("related_gaps", []),
            "priority": 1,
            "asked": False,
            "topic_id": topic.get("id"),
            "is_follow_up": False,
        }]


async def generate_discovery_prompts(state: ResumeState) -> list[dict]:
    """Generate discovery prompts based on gap analysis.

    Creates at least 5 prompts ordered by relevance to highest-priority gaps.
    Uses raw text for better LLM context instead of formatted structured data.
    """
    gap_analysis = state.get("gap_analysis", {})

    # Prefer raw text fields for LLM context
    profile_text = state.get("profile_text") or state.get("profile_markdown") or ""
    job_text = state.get("job_text") or state.get("job_markdown") or ""

    # Get metadata - prefer extracted fields, fall back to structured data
    user_profile = state.get("user_profile", {})
    job_posting = state.get("job_posting", {})

    if not gap_analysis:
        logger.warning("No gap analysis found, cannot generate discovery prompts")
        return []

    # Build context for prompt generation
    gaps = gap_analysis.get("gaps", [])
    gaps_detailed = gap_analysis.get("gaps_detailed", [])
    opportunities = gap_analysis.get("opportunities", [])

    # Get job info - prefer state fields, fall back to structured
    job_title = state.get("job_title") or job_posting.get("title", "the target role")
    company_name = state.get("job_company") or job_posting.get("company_name", "the company")
    requirements = job_posting.get("requirements", [])

    # Get user info
    user_name = state.get("profile_name") or user_profile.get("name", "the candidate")

    # Use raw text for profile context (truncate to reasonable size for LLM)
    profile_context = profile_text[:4000] if profile_text else ""

    # Determine seniority from raw text using heuristics
    seniority = estimate_seniority(profile_text)

    if seniority == "early_career":
        seniority_guidance = """
## SENIORITY: EARLY CAREER (0-2 years)
This person is JUNIOR. Questions should:
- Frame their work as valuable: "2 years of dense agency work IS experience"
- Look for small wins with unexpectedly big impact
- Explore times they helped others or got asked questions
- Find moments they went beyond just completing tickets
- Ask what made THEIR fix/approach different
- AVOID undermining language like "even as a junior"

GOOD questions for juniors (SHORT - 15 words max):
- "Slowest client site at AgencyWeb - what did YOU find was causing the bottleneck?"
- "Small fix you built that seemed too minor to mention - what would have broken without it?"
- "When tickets got stuck, did people come to YOU? What problems did you crack?"
- "What did you spot in the code that senior devs overlooked?"
"""
    elif seniority == "mid_level":
        seniority_guidance = """
## SENIORITY: MID-LEVEL (3-5 years)
Questions should:
- Surface ownership and initiative beyond assigned work
- Find collaboration stories with cross-functional teams
- Explore technical decisions they influenced
- Look for mentoring or knowledge sharing
- Ask what made THEIR approach different from what others tried
- For career changers: Bridge their domain expertise to engineering value

GOOD questions for mid-level (STRONG affirmation + direct bridge + probe):
- "With 3+ years at [company], you've seen patterns others miss - what would have broken if you'd done it the standard way?"
- "[Achievement] at [company] required technical judgment - walk me through a decision you made that engineers later validated."
- "Leading cross-functional teams = translating between eng and business = API design. When did you shape how a feature was built?"
- "Growing DAU 3x at StartupXYZ - you were making data infrastructure decisions whether you called it that or not. What did YOU see in the data?"
- "At [company], SQL queries you wrote for analysis - which ones became features or dashboards engineers productionized?"
"""
    else:  # seniority == "senior"
        seniority_guidance = """
## SENIORITY: SENIOR (5+ years)
Questions should:
- START with strong affirmation: "Mentoring juniors at TechCorp is exactly what Staff engineers do..."
- Surface cross-team influence (CRITICAL for Staff roles)
- Ask for QUANTIFIABLE SCALE in a friendly way
- Keep questions SHORT (1 sentence ideal, 2 max)
- Include escape hatches for pivoting

GOOD questions for senior (Staff-level differentiation) - NOTE THE AFFIRMATION + BREVITY:
- "Mentoring juniors at TechCorp is exactly the multiplier Staff roles need - what breakthrough did you help someone have?"
- "Building microservices means you've already done system design - what tradeoff are you secretly proud of?"
- "3 years at TechCorp made you the person others turn to - what's your secret weapon for debugging?"
- "Your cross-team work at TechCorp is Staff-level impact - how many teams did your decisions affect?"
- ESCAPE HATCH: "If cross-team work isn't ringing a bell, think about times you helped engineers outside your immediate team."
"""

    prompt = f"""You are a warm, experienced career coach helping {user_name} prepare for {job_title} at {company_name}.

## CORE PHILOSOPHY: Strength-First, Not Deficit-First
NEVER make them feel like they're missing something. Instead:
- Show how their EXISTING experience is MORE relevant than they think
- Build bridges from what they HAVE to what the job NEEDS
- Help them see value they didn't realize was there

CRITICAL RULE: Only ask about experiences CONFIRMED in their profile.
- If they're a backend engineer, don't ASSERT they've done frontend - ASK if they have
- PROBE for hidden experience, don't ASSUME it exists
- BAD: "At DataCorp you built admin UIs..." (assumes frontend work not in profile)
- GOOD: "Building REST APIs = thinking about consumers. Did you ever see frontend struggling with your design?"

BAD: "You don't have leadership experience - tell me about any leadership you might have done"
GOOD: "Managing 5 client projects at AgencyWeb is basically leadership - what kept those from going off the rails?"

{seniority_guidance}

## GAPS TO ADDRESS (build bridges from existing experience to these requirements)
{chr(10).join(f"- {g}" for g in gaps[:5])}

## JOB REQUIREMENTS (what they connect to)
{chr(10).join(f"- {r}" for r in requirements[:5]) if requirements else "See job description below"}

## {user_name}'S PROFILE/RESUME (raw text - reference specific companies and achievements from this)
{profile_context if profile_context else "No profile text available"}

## QUESTION STRUCTURE (20 WORDS MAX - specific + punchy)

Pattern: [Name their company/achievement] + [Bridge to job requirement] + [Incisive probe]

CRITICAL: Always reference SPECIFIC companies and achievements from their profile, not generic patterns.

GOOD (18 words): "3 years building microservices at TechCorp - that's Staff-level system design already. What tradeoff are you proudest of?"
GOOD (17 words): "Growing DAU 3x at StartupXYZ required data decisions - when did your analysis reveal something engineering missed?"
GOOD (16 words): "At AgencyWeb, fixing bugs across client projects = performance debugging. What bug made you feel like a detective?"
BAD (generic): "Agency work means variety..." - missing specific company name
BAD (30+ words): Long rambling question with no specific references

## CONVERSATIONAL AGILITY - Move Fast, Pivot When Dry
- Get to the point quickly - no 3-sentence warmups
- Include escape hatches: "If that's not ringing a bell, think about..."
- Don't linger - if one angle isn't working, try another
- Quality over quantity - one great question beats three mediocre ones

## BRIDGE-BUILDING QUESTIONS (20 words max, MUST use their company/achievement names):
- "At AgencyWeb, you debugged across client projects - that's performance optimization. What bug made you a detective?"
- "6 years of patient handoffs at Healthcare Inc = incident response. What made smooth vs dangerous?"
- "At TechCorp mentoring juniors - that's the multiplier Staff roles need. When did teaching unlock YOUR understanding?"

ESCAPE HATCHES (add when the angle might not land):
- "...or if [alternative angle] is more your thing..."
- "What about times when..." (positive pivot to new angle)

## WHAT TANKS YOUR SCORE (avoid at all costs):
- "Tell me about a time when..." (sounds like HR interview)
- "You're missing X - tell me about X" (deficit framing)
- Generic questions with no personal context
- Yes/no questions: "Did you ever...?" → "What happened when...?" or "Walk me through..."
- Long, complex questions (keep it to 1-2 sentences)
- Questions about things already clearly on their resume
- Assuming experiences not in profile without escape hatch

PIVOT TECHNIQUE: If a topic might not land, add a positive pivot (NOT negative "if not"):
- GOOD: "...or if debugging is more your thing, when did you crack something others couldn't?"
- BAD: "If that's not ringing a bell..." (sounds defeatist)

## OUTPUT
Return JSON array with 5-6 varied questions:
[
  {{
    "question": "Your thoughtfully crafted question here",
    "intent": "What hidden value this surfaces",
    "related_gaps": ["Which gap this addresses"],
    "priority": 1
  }}
]
"""

    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract JSON from response
        content = response.content[0].text
        prompts_data = _extract_json_from_response(content)

        # Convert to DiscoveryPrompt objects
        prompts = []
        for i, p in enumerate(prompts_data):
            prompt_obj = DiscoveryPrompt(
                id=str(uuid.uuid4()),
                question=p.get("question", ""),
                intent=p.get("intent", ""),
                related_gaps=p.get("related_gaps", []),
                priority=p.get("priority", i + 1),
                asked=False,
            )
            prompts.append(prompt_obj.model_dump())

        logger.info(f"Generated {len(prompts)} discovery prompts")
        return prompts

    except Exception as e:
        logger.error(f"Failed to generate discovery prompts: {e}")
        # Return fallback prompts
        return _get_fallback_prompts(gaps)


def _get_fallback_prompts(gaps: list[str]) -> list[dict]:
    """Generate fallback prompts if LLM fails - executive coach style."""
    fallback_questions = [
        {
            "question": "Think about a time when something at work was clearly broken or inefficient, and you were the one who decided to fix it - even though nobody asked you to. What was the situation, and what did you actually do?",
            "intent": "Surface initiative and ownership beyond formal responsibilities",
            "related_gaps": gaps[:1] if gaps else [],
            "priority": 1,
        },
        {
            "question": "When was the last time you had to convince someone more senior than you - or someone who didn't report to you - to change their mind about something important? What was at stake, and how did you approach it?",
            "intent": "Uncover influence and stakeholder management skills",
            "related_gaps": gaps[1:2] if len(gaps) > 1 else [],
            "priority": 2,
        },
        {
            "question": "What's something you built, created, or improved that you're secretly proud of - even if it never made it into your resume because it seemed too small or 'just part of the job'?",
            "intent": "Surface undervalued achievements and craftsmanship",
            "related_gaps": gaps[2:3] if len(gaps) > 2 else [],
            "priority": 3,
        },
        {
            "question": "Tell me about a time when a project or initiative was about to fail, and you were the person who figured out how to save it. What did everyone else miss that you caught?",
            "intent": "Reveal problem-solving under pressure and unique contributions",
            "related_gaps": gaps[3:4] if len(gaps) > 3 else [],
            "priority": 4,
        },
        {
            "question": "Outside of your main job duties, when have you taken on something - a side project, volunteer work, a personal challenge - that pushed you to develop skills you wouldn't normally use at work?",
            "intent": "Discover transferable skills from non-traditional experiences",
            "related_gaps": gaps[4:5] if len(gaps) > 4 else [],
            "priority": 5,
        },
    ]

    prompts = []
    for p in fallback_questions:
        prompt_obj = DiscoveryPrompt(
            id=str(uuid.uuid4()),
            question=p["question"],
            intent=p["intent"],
            related_gaps=p["related_gaps"],
            priority=p["priority"],
            asked=False,
        )
        prompts.append(prompt_obj.model_dump())

    return prompts


async def process_discovery_response(
    user_response: str,
    current_prompt: dict,
    state: ResumeState,
) -> dict:
    """Process a user's response to a discovery prompt.

    Returns:
        dict with:
            - extracted_experiences: list of discovered experiences
            - follow_up: optional follow-up question
            - move_to_next: whether to move to next prompt
            - topic_coverage: "covered" | "partial" | "none" - how well this topic was addressed
            - move_to_next_topic: whether to advance to the next agenda topic
    """
    job_posting = state.get("job_posting", {})
    gap_analysis = state.get("gap_analysis", {})
    discovery_agenda = state.get("discovery_agenda", {})

    requirements = job_posting.get("requirements", [])
    gaps = gap_analysis.get("gaps", [])

    # Get current topic info for context
    current_topic = None
    if discovery_agenda and current_prompt.get("topic_id"):
        for topic in discovery_agenda.get("topics", []):
            if topic.get("id") == current_prompt.get("topic_id"):
                current_topic = topic
                break

    topic_context = ""
    if current_topic:
        topic_context = f"""
## CURRENT TOPIC: {current_topic.get('title', 'Discovery')}
Goal: {current_topic.get('goal', '')}
Prompts asked for this topic: {current_topic.get('prompts_asked', 0)}/{current_topic.get('max_prompts', 2)}
"""

    prompt = f"""You are a senior executive career coach analyzing a candidate's response.
{topic_context}

## The Question Asked
{current_prompt.get('question', '')}

## What We Were Looking For
Intent: {current_prompt.get('intent', '')}
Strengths to amplify: {', '.join(current_prompt.get('related_gaps', []))}

## Target Job Requirements
{chr(10).join(f"- {r}" for r in requirements[:5])}

## The Candidate's Response
{user_response}

## Your Analysis Task

1. **Extract achievement stories**: Look for concrete examples with results. A good story has:
   - What was the situation/challenge?
   - What did THEY specifically do (not the team)?
   - What was the measurable or meaningful impact?

2. **MOVE FAST - Pivot or Dig Based on Signals**:

   **PIVOT (move_to_next = true) when you see:**
   - Short, vague answers: "Not really", "I guess", "Nothing comes to mind"
   - They're reaching/fabricating: "I suppose I could say..."
   - Repeating the same story they already told
   - Generic answers without specifics
   - Already asked 2+ questions on this topic

   **DIG DEEPER (move_to_next = false) ONLY when:**
   - They mentioned something juicy but glossed over the impact
   - There's clearly more gold to mine
   - They gave a rich answer that hints at even more

   **Default to PIVOT** - better to explore fresh angles than over-interrogate

3. **Follow-ups must be SHORT (1 sentence max)**:
   - BAD: "Can you tell me more?"
   - BAD: "That's interesting. Let me understand..." (too long)
   - GOOD: "What would have broken if you hadn't stepped in?"
   - GOOD: "How many users/teams did that affect?"

4. **Topic Coverage Assessment** (if we're tracking a specific topic):
   - "covered": They gave substantial, concrete experiences for this topic
   - "partial": Some useful info but more could be extracted
   - "none": Vague, off-topic, or no actionable content

5. **Move to Next Topic** (separate from move_to_next prompt):
   - Set to true if: topic is well-covered, OR we've asked max prompts for this topic, OR topic clearly isn't resonating
   - Set to false if: there's more to explore within this topic

## Output Format
{{
  "experiences": [
    {{
      "description": "Concise achievement statement suitable for a resume bullet",
      "source_quote": "Their exact words that support this",
      "mapped_requirements": ["Which job requirements this addresses"]
    }}
  ],
  "follow_up": "SHORT follow-up (1 sentence max) if needed, or null",
  "move_to_next": true/false,  // Move to next prompt (within same topic)
  "topic_coverage": "covered" | "partial" | "none",  // How well was this topic addressed
  "move_to_next_topic": true/false  // Should we move to the next agenda topic?
}}

Be generous extracting experiences. Be aggressive about pivoting - don't linger when the well is dry.
"""

    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        result = _extract_json_from_response(content)

        # Convert experiences to proper format
        experiences = []
        for exp in result.get("experiences", []):
            exp_obj = DiscoveredExperience(
                id=str(uuid.uuid4()),
                description=exp.get("description", ""),
                source_quote=exp.get("source_quote", ""),
                mapped_requirements=exp.get("mapped_requirements", []),
            )
            experiences.append(exp_obj.model_dump())

        # Determine topic coverage - default to "partial" if not specified
        topic_coverage = result.get("topic_coverage", "partial")
        move_to_next_topic = result.get("move_to_next_topic", False)

        # If we have a current topic and reached max prompts, force move to next topic
        if current_topic and current_topic.get("prompts_asked", 0) >= current_topic.get("max_prompts", 2):
            move_to_next_topic = True

        return {
            "extracted_experiences": experiences,
            "follow_up": result.get("follow_up"),
            "move_to_next": result.get("move_to_next", True),
            "topic_coverage": topic_coverage,
            "move_to_next_topic": move_to_next_topic,
        }

    except Exception as e:
        logger.error(f"Failed to process discovery response: {e}")
        return {
            "extracted_experiences": [],
            "follow_up": None,
            "move_to_next": True,
            "topic_coverage": "none",
            "move_to_next_topic": True,  # Move on if processing fails
        }


def get_next_prompt(state: ResumeState) -> Optional[dict]:
    """Get the next unasked discovery prompt."""
    prompts = state.get("discovery_prompts", [])

    for prompt in prompts:
        if not prompt.get("asked", False):
            return prompt

    return None


async def discovery_node(state: ResumeState) -> dict:
    """Main discovery node for the workflow.

    Uses a state-based phase tracking approach with agenda-based questioning:
    - Phase "setup": Generate agenda/prompts, add message, set phase to "waiting", return state
    - Phase "waiting": Call interrupt(), process response, update state

    The agenda system:
    1. Generates 5-6 high-level topics from gap analysis
    2. Generates 1-2 prompts per topic (not all upfront)
    3. Tracks topic coverage and transitions between topics
    """
    from langgraph.types import interrupt

    discovery_prompts = list(state.get("discovery_prompts", []))
    discovery_messages = list(state.get("discovery_messages", []))
    discovered_experiences = list(state.get("discovered_experiences", []))
    discovery_exchanges = state.get("discovery_exchanges", 0)
    discovery_confirmed = state.get("discovery_confirmed", False)
    discovery_phase = state.get("discovery_phase", "setup")
    pending_prompt_id = state.get("pending_prompt_id")
    discovery_agenda = state.get("discovery_agenda") or {}

    # Check if discovery is already confirmed
    if discovery_confirmed:
        logger.info("Discovery already confirmed, proceeding to next step")
        return {
            "current_step": "qa",
            "discovery_phase": None,
            "pending_prompt_id": None,
            "updated_at": datetime.now().isoformat(),
        }

    # === SETUP PHASE: Generate agenda/prompts and prepare for interrupt ===
    if discovery_phase == "setup" or not discovery_prompts:
        # Generate agenda on first entry
        if not discovery_agenda or not discovery_agenda.get("topics"):
            logger.info("Generating discovery agenda from gap analysis")
            discovery_agenda = await generate_discovery_agenda(state)

            if not discovery_agenda.get("topics"):
                logger.warning("No topics generated, skipping discovery")
                return {
                    "discovery_agenda": discovery_agenda,
                    "discovery_prompts": [],
                    "discovery_confirmed": True,
                    "current_step": "qa",
                    "updated_at": datetime.now().isoformat(),
                }

        # Get current topic
        current_topic = None
        current_topic_id = discovery_agenda.get("current_topic_id")
        for topic in discovery_agenda.get("topics", []):
            if topic.get("id") == current_topic_id:
                current_topic = topic
                break

        # If no current topic, find the next pending one
        if not current_topic:
            for topic in discovery_agenda.get("topics", []):
                if topic.get("status") in ["pending", "in_progress"]:
                    current_topic = topic
                    current_topic["status"] = "in_progress"
                    discovery_agenda["current_topic_id"] = topic["id"]
                    break

        # If no pending topics, all topics complete
        if not current_topic:
            logger.info("All agenda topics covered")
            discovery_agenda["covered_topics"] = discovery_agenda["total_topics"]
            return {
                "discovery_agenda": discovery_agenda,
                "discovery_prompts": discovery_prompts,
                "discovery_confirmed": True,
                "current_step": "qa",
                "sub_step": None,
                "discovery_phase": None,
                "pending_prompt_id": None,
                "updated_at": datetime.now().isoformat(),
            }

        # Generate prompts for current topic if needed
        topic_prompts = [p for p in discovery_prompts
                        if p.get("topic_id") == current_topic["id"] and not p.get("asked", False)]

        if not topic_prompts:
            # Check if we've asked max prompts for this topic
            if current_topic.get("prompts_asked", 0) >= current_topic.get("max_prompts", 2):
                # Move to next topic
                current_topic["status"] = "covered"
                discovery_agenda["covered_topics"] = sum(
                    1 for t in discovery_agenda.get("topics", [])
                    if t.get("status") in ["covered", "skipped"]
                )
                discovery_agenda["current_topic_id"] = None

                # Recurse to get next topic
                return await discovery_node({
                    **state,
                    "discovery_agenda": discovery_agenda,
                    "discovery_prompts": discovery_prompts,
                    "discovery_phase": "setup",
                })

            # Generate new prompts for this topic
            logger.info(f"Generating prompts for topic '{current_topic.get('title')}'")
            new_prompts = await generate_topic_prompts(state, current_topic)
            discovery_prompts.extend(new_prompts)
            topic_prompts = new_prompts

        # Find next unasked prompt for current topic
        current_prompt = None
        for p in topic_prompts:
            if not p.get("asked", False):
                current_prompt = p
                break

        if not current_prompt:
            # Fallback: get any unasked prompt
            current_prompt = get_next_prompt({"discovery_prompts": discovery_prompts})

        if not current_prompt:
            # All prompts asked, complete discovery
            logger.info("All discovery prompts asked")
            return {
                "discovery_agenda": discovery_agenda,
                "discovery_prompts": discovery_prompts,
                "discovery_confirmed": True,
                "current_step": "qa",
                "sub_step": None,
                "discovery_phase": None,
                "pending_prompt_id": None,
                "updated_at": datetime.now().isoformat(),
            }

        # Mark prompt as asked and increment topic counter
        for p in discovery_prompts:
            if p["id"] == current_prompt["id"]:
                p["asked"] = True
                break

        current_topic["prompts_asked"] = current_topic.get("prompts_asked", 0) + 1

        # Add agent message for this prompt
        agent_message = DiscoveryMessage(
            role="agent",
            content=current_prompt["question"],
            prompt_id=current_prompt["id"],
        ).model_dump()
        discovery_messages.append(agent_message)

        # Count prompts asked
        asked_count = sum(1 for p in discovery_prompts if p.get("asked", False))

        # Build interrupt payload with agenda info
        interrupt_payload = {
            "interrupt_type": "discovery_prompt",
            "message": current_prompt["question"],
            "context": {
                "intent": current_prompt.get("intent", ""),
                "related_gaps": current_prompt.get("related_gaps", []),
                "prompt_number": asked_count,
                "total_prompts": len(discovery_prompts),
                "exchanges_completed": discovery_exchanges,
                # Agenda info for frontend
                "current_topic": {
                    "id": current_topic.get("id"),
                    "title": current_topic.get("title"),
                    "goal": current_topic.get("goal"),
                    "prompts_asked": current_topic.get("prompts_asked", 0),
                    "max_prompts": current_topic.get("max_prompts", 2),
                },
                "agenda_progress": {
                    "covered_topics": discovery_agenda.get("covered_topics", 0),
                    "total_topics": discovery_agenda.get("total_topics", 0),
                },
            },
            "can_skip": True,
        }

        # Return state with phase="waiting" - graph will loop back
        logger.info(f"Discovery setup complete, asking prompt {asked_count} for topic '{current_topic.get('title')}'")
        return {
            "discovery_agenda": discovery_agenda,
            "discovery_prompts": discovery_prompts,
            "discovery_messages": discovery_messages,
            "discovered_experiences": discovered_experiences,
            "discovery_exchanges": discovery_exchanges,
            "current_step": "discovery",
            "sub_step": "awaiting_response",
            "discovery_phase": "waiting",
            "pending_prompt_id": current_prompt["id"],
            "pending_interrupt": interrupt_payload,
            "updated_at": datetime.now().isoformat(),
        }

    # === WAITING PHASE: Call interrupt and process response ===
    if discovery_phase == "waiting":
        # Find the prompt we're waiting on
        current_prompt = None
        for p in discovery_prompts:
            if p["id"] == pending_prompt_id:
                current_prompt = p
                break

        if not current_prompt:
            logger.error(f"Pending prompt {pending_prompt_id} not found")
            return {
                "discovery_phase": "setup",
                "pending_prompt_id": None,
                "updated_at": datetime.now().isoformat(),
            }

        # Get current topic for context
        current_topic = None
        current_topic_id = discovery_agenda.get("current_topic_id")
        for topic in discovery_agenda.get("topics", []):
            if topic.get("id") == current_topic_id:
                current_topic = topic
                break

        # Rebuild interrupt payload with agenda info
        asked_count = sum(1 for p in discovery_prompts if p.get("asked", False))
        interrupt_payload = {
            "interrupt_type": "discovery_prompt",
            "message": current_prompt["question"],
            "context": {
                "intent": current_prompt.get("intent", ""),
                "related_gaps": current_prompt.get("related_gaps", []),
                "prompt_number": asked_count,
                "total_prompts": len(discovery_prompts),
                "exchanges_completed": discovery_exchanges,
                # Agenda info for frontend
                "current_topic": {
                    "id": current_topic.get("id") if current_topic else None,
                    "title": current_topic.get("title") if current_topic else None,
                    "goal": current_topic.get("goal") if current_topic else None,
                    "prompts_asked": current_topic.get("prompts_asked", 0) if current_topic else 0,
                    "max_prompts": current_topic.get("max_prompts", 2) if current_topic else 2,
                },
                "agenda_progress": {
                    "covered_topics": discovery_agenda.get("covered_topics", 0),
                    "total_topics": discovery_agenda.get("total_topics", 0),
                },
            },
            "can_skip": True,
        }

        # Call interrupt to wait for user response
        user_response = interrupt(interrupt_payload)

        # Process user response with agenda context
        result = await _handle_user_response(
            user_response,
            current_prompt,
            state,
            discovery_agenda,
        )

        # Set phase back to "setup" to get next prompt
        result["discovery_phase"] = "setup"
        result["pending_prompt_id"] = None

        return result

    # Fallback - reset to setup phase
    return {
        "discovery_phase": "setup",
        "updated_at": datetime.now().isoformat(),
    }


async def _handle_user_response(
    user_response: str,
    current_prompt: dict,
    state: ResumeState,
    discovery_agenda: dict = None,
) -> dict:
    """Handle user response to a discovery prompt.

    Features:
    - Adaptive questioning: follow-ups inserted as needed
    - Topic tracking: experiences linked to current topic
    - Topic transitions: moves to next topic when appropriate
    """
    discovery_messages = list(state.get("discovery_messages", []))
    discovered_experiences = list(state.get("discovered_experiences", []))
    discovery_exchanges = state.get("discovery_exchanges", 0)
    discovery_prompts = list(state.get("discovery_prompts", []))
    discovery_agenda = discovery_agenda or state.get("discovery_agenda", {})

    # Check for completion signals - end discovery and go directly to draft
    if user_response.lower().strip() in ["done", "complete", "finish"]:
        return {
            "discovery_confirmed": True,
            "user_done_signal": True,  # Also skip QA phase
            "qa_complete": True,
            "current_step": "draft",  # Go directly to drafting
            "sub_step": None,
            "updated_at": datetime.now().isoformat(),
        }

    # Handle "skip" — skip the current question/topic, move to the next one
    is_skip = user_response.lower().strip() == "skip"

    # Add user message
    user_message = DiscoveryMessage(
        role="user",
        content="(Skipped)" if is_skip else user_response,
    ).model_dump()
    discovery_messages.append(user_message)

    if is_skip:
        # Mark current topic as skipped and move on
        discovery_exchanges += 1
        if discovery_agenda and current_prompt.get("topic_id"):
            current_topic_id = current_prompt.get("topic_id")
            for topic in discovery_agenda.get("topics", []):
                if topic.get("id") == current_topic_id:
                    topic["status"] = "skipped"
                    discovery_agenda["covered_topics"] = sum(
                        1 for t in discovery_agenda.get("topics", [])
                        if t.get("status") in ["covered", "skipped"]
                    )
                    discovery_agenda["current_topic_id"] = None
                    logger.info(f"Topic '{topic.get('title')}' skipped by user")
                    break
        return {
            "discovery_agenda": discovery_agenda,
            "discovery_prompts": discovery_prompts,
            "discovery_messages": discovery_messages,
            "discovered_experiences": discovered_experiences,
            "discovery_exchanges": discovery_exchanges,
            "updated_at": datetime.now().isoformat(),
        }

    # Process response with agenda context
    result = await process_discovery_response(user_response, current_prompt, state)

    # Add extracted experiences
    new_experiences = result.get("extracted_experiences", [])
    if new_experiences:
        # Update user message with experience IDs
        user_message["experiences_extracted"] = [e["id"] for e in new_experiences]
        discovery_messages[-1] = user_message
        discovered_experiences.extend(new_experiences)

        # Link experiences to current topic
        current_topic_id = current_prompt.get("topic_id")
        if current_topic_id and discovery_agenda:
            for topic in discovery_agenda.get("topics", []):
                if topic.get("id") == current_topic_id:
                    topic["experiences_found"] = topic.get("experiences_found", [])
                    topic["experiences_found"].extend([e["id"] for e in new_experiences])
                    break

    # Increment exchange count
    discovery_exchanges += 1

    # Handle topic transitions
    move_to_next_topic = result.get("move_to_next_topic", False)
    topic_coverage = result.get("topic_coverage", "partial")

    if discovery_agenda and current_prompt.get("topic_id"):
        current_topic_id = current_prompt.get("topic_id")
        for topic in discovery_agenda.get("topics", []):
            if topic.get("id") == current_topic_id:
                # Check if we should move to next topic
                if move_to_next_topic or topic.get("prompts_asked", 0) >= topic.get("max_prompts", 2):
                    # Mark topic as covered based on coverage
                    if topic_coverage == "covered" or new_experiences:
                        topic["status"] = "covered"
                    elif topic_coverage == "none":
                        topic["status"] = "skipped"
                    else:
                        topic["status"] = "covered"  # Default to covered

                    # Update covered count
                    discovery_agenda["covered_topics"] = sum(
                        1 for t in discovery_agenda.get("topics", [])
                        if t.get("status") in ["covered", "skipped"]
                    )
                    discovery_agenda["current_topic_id"] = None
                    logger.info(f"Topic '{topic.get('title')}' marked as {topic['status']}")
                break

    # Handle adaptive follow-up questions
    follow_up = result.get("follow_up")
    move_to_next = result.get("move_to_next", True)

    # If LLM suggested a follow-up and we shouldn't move on, insert it as next question
    # But only if we haven't moved to the next topic
    # Also enforce max prompts limit to prevent unbounded growth
    MAX_PROMPTS = 50
    if follow_up and not move_to_next and not move_to_next_topic and discovery_exchanges < 10:
        if len(discovery_prompts) >= MAX_PROMPTS:
            logger.warning(f"Discovery prompts limit reached ({MAX_PROMPTS}), skipping follow-up")
        else:
            # Create a follow-up prompt with the same topic_id
            follow_up_prompt = {
                "id": f"followup_{uuid.uuid4().hex[:8]}",
                "question": follow_up,
                "intent": f"Follow up on: {current_prompt.get('intent', '')}",
                "related_gaps": current_prompt.get("related_gaps", []),
                "priority": 0,  # Highest priority - ask next
                "asked": False,
                "topic_id": current_prompt.get("topic_id"),  # Keep same topic
                "is_follow_up": True,  # Mark as dynamically generated
            }

            # Insert at the beginning so it's asked next
            discovery_prompts.insert(0, follow_up_prompt)
            logger.info(f"Inserted adaptive follow-up question: {follow_up[:50]}...")

    return {
        "discovery_agenda": discovery_agenda,
        "discovery_prompts": discovery_prompts,
        "discovery_messages": discovery_messages,
        "discovered_experiences": discovered_experiences,
        "discovery_exchanges": discovery_exchanges,
        "updated_at": datetime.now().isoformat(),
    }
