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
)
from config import get_settings

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


async def generate_discovery_prompts(state: ResumeState) -> list[dict]:
    """Generate discovery prompts based on gap analysis.

    Creates at least 5 prompts ordered by relevance to highest-priority gaps.
    """
    gap_analysis = state.get("gap_analysis", {})
    user_profile = state.get("user_profile", {})
    job_posting = state.get("job_posting", {})

    if not gap_analysis:
        logger.warning("No gap analysis found, cannot generate discovery prompts")
        return []

    # Build context for prompt generation
    gaps = gap_analysis.get("gaps", [])
    gaps_detailed = gap_analysis.get("gaps_detailed", [])
    opportunities = gap_analysis.get("opportunities", [])

    job_title = job_posting.get("title", "the target role")
    company_name = job_posting.get("company_name", "the company")
    requirements = job_posting.get("requirements", [])

    user_name = user_profile.get("name", "the candidate")
    experiences = user_profile.get("experience", [])

    # Build experience summary for context
    experience_summary = ""
    for exp in experiences[:3]:
        experience_summary += f"- {exp.get('position', 'Role')} at {exp.get('company', 'Company')}\n"

    prompt = f"""You are a senior executive career coach with 20+ years experience helping high performers land roles at top companies. Your approach is Socratic - you ask incisive questions that make candidates suddenly realize "Oh, I never thought of that as an achievement worth mentioning!"

You're helping {user_name} prepare for {job_title} at {company_name}. Your job is to unearth hidden gold - the achievements, initiatives, and impact they've undervalued or forgotten.

## The Gaps We Need to Address
{chr(10).join(f"- {g}" for g in gaps[:5])}

## Opportunities Worth Exploring
{chr(10).join(f"- {o.get('description', o) if isinstance(o, dict) else o}" for o in opportunities[:3])}

## What {company_name} is Looking For
{chr(10).join(f"- {r}" for r in requirements[:5])}

## What We Know About {user_name}
{experience_summary}

## Your Coaching Approach
Generate 5-7 discovery questions that will make {user_name} think differently about their experience:

1. **Dig for hidden impact** - Don't ask "did you lead a team?" Ask about moments when they stepped up, influenced outcomes, or drove change even without the title
2. **Challenge assumptions** - Many people dismiss their achievements as "just part of the job." Help them see the exceptional in what they consider ordinary
3. **Be specific and provocative** - Instead of "tell me about a challenge," ask about specific scenarios: "When did you have to convince skeptics? What was on the line?"
4. **Uncover transferable moments** - Even if they lack exact experience, probe for adjacent situations that demonstrate the same capability
5. **Focus on stories, not skills** - Stories are memorable. Ask questions that prompt narrative responses with conflict, action, and results

## Question Style Examples
- BAD: "Do you have leadership experience?" (generic, yes/no, boring)
- GOOD: "Think about a time when a project was about to fail and you were the one who rallied people around a solution. What did you do that no one else was doing?"

- BAD: "Tell me about your technical skills" (resume regurgitation)
- GOOD: "What's a technical problem you solved that you're secretly proud of, even if it never made it into your resume because it seemed too small?"

- BAD: "Have you worked with cross-functional teams?" (checkbox question)
- GOOD: "When have you had to get someone who didn't report to you - maybe in a completely different department - to care about your priority? How did you make that happen?"

## Output Format
Return a JSON array with questions that will make {user_name} pause and think:
[
  {{
    "question": "When was the last time you fixed something that wasn't technically your responsibility, just because you couldn't stand watching it stay broken? What happened?",
    "intent": "Surface initiative and ownership mindset beyond role boundaries",
    "related_gaps": ["Relevant gap this addresses"],
    "priority": 1
  }}
]

Make every question impossible to answer with a simple "yes" or "no". Each should prompt a story.
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
    """
    job_posting = state.get("job_posting", {})
    gap_analysis = state.get("gap_analysis", {})

    requirements = job_posting.get("requirements", [])
    gaps = gap_analysis.get("gaps", [])

    prompt = f"""You are a senior executive career coach analyzing a candidate's response to extract resume-worthy achievements and determine if a follow-up would unearth more gold.

## The Question Asked
{current_prompt.get('question', '')}

## What We Were Looking For
Intent: {current_prompt.get('intent', '')}
Gaps to address: {', '.join(current_prompt.get('related_gaps', []))}

## Target Job Requirements
{chr(10).join(f"- {r}" for r in requirements[:5])}

## The Candidate's Response
{user_response}

## Your Analysis Task

1. **Extract achievement stories**: Look for concrete examples with results, not just activities. A good story has:
   - What was the situation/challenge?
   - What did THEY specifically do (not the team)?
   - What was the measurable or meaningful impact?

2. **Decide if we should dig deeper**:
   - If they gave a vague answer ("I've done that before"), ask for a SPECIFIC instance
   - If they mentioned something interesting but glossed over the impact, probe the results
   - If they revealed a rich story with clear impact, move on - don't over-interview them
   - If they said very little, ask a different, more specific version of the question

3. **If you ask a follow-up, make it sharp**:
   - BAD: "Can you tell me more?" (lazy, generic)
   - GOOD: "You mentioned rallying the team during the outage - what specifically did you do that calmed people down? What would have happened if you hadn't stepped in?"

## Output Format
{{
  "experiences": [
    {{
      "description": "Concise achievement statement suitable for a resume bullet",
      "source_quote": "Their exact words that support this",
      "mapped_requirements": ["Which job requirements this addresses"]
    }}
  ],
  "follow_up": "Your incisive follow-up question if needed, or null if the response was comprehensive",
  "move_to_next": true/false  // true if we got what we need, false if follow-up is warranted
}}

Be generous in extracting experiences - even partial stories can become great resume bullets. But be strategic about follow-ups: only ask if there's clearly more gold to mine.
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

        return {
            "extracted_experiences": experiences,
            "follow_up": result.get("follow_up"),
            "move_to_next": result.get("move_to_next", True),
        }

    except Exception as e:
        logger.error(f"Failed to process discovery response: {e}")
        return {
            "extracted_experiences": [],
            "follow_up": None,
            "move_to_next": True,
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

    Uses a state-based phase tracking approach:
    - Phase "setup": Generate prompts, add message, set phase to "waiting", return state
    - Phase "waiting": Call interrupt(), process response, update state

    This ensures state is persisted BEFORE the interrupt by returning early
    and letting the graph loop back.
    """
    from langgraph.types import interrupt

    discovery_prompts = list(state.get("discovery_prompts", []))
    discovery_messages = list(state.get("discovery_messages", []))
    discovered_experiences = list(state.get("discovered_experiences", []))
    discovery_exchanges = state.get("discovery_exchanges", 0)
    discovery_confirmed = state.get("discovery_confirmed", False)
    discovery_phase = state.get("discovery_phase", "setup")
    pending_prompt_id = state.get("pending_prompt_id")

    # Check if discovery is already confirmed
    if discovery_confirmed:
        logger.info("Discovery already confirmed, proceeding to next step")
        return {
            "current_step": "qa",
            "discovery_phase": None,
            "pending_prompt_id": None,
            "updated_at": datetime.now().isoformat(),
        }

    # === SETUP PHASE: Generate prompts and prepare for interrupt ===
    if discovery_phase == "setup" or not discovery_prompts:
        # Generate prompts on first entry
        if not discovery_prompts:
            logger.info("Generating discovery prompts from gap analysis")
            prompts = await generate_discovery_prompts(state)

            if not prompts:
                logger.warning("No prompts generated, skipping discovery")
                return {
                    "discovery_prompts": [],
                    "discovery_confirmed": True,
                    "current_step": "qa",
                    "updated_at": datetime.now().isoformat(),
                }

            discovery_prompts = prompts

        # Find next unasked prompt
        current_prompt = get_next_prompt({"discovery_prompts": discovery_prompts})

        if not current_prompt:
            # All prompts asked, complete discovery
            logger.info("All discovery prompts asked")
            return {
                "discovery_prompts": discovery_prompts,
                "discovery_confirmed": True,
                "current_step": "qa",
                "sub_step": None,
                "discovery_phase": None,
                "pending_prompt_id": None,
                "updated_at": datetime.now().isoformat(),
            }

        # Mark prompt as asked
        for p in discovery_prompts:
            if p["id"] == current_prompt["id"]:
                p["asked"] = True
                break

        # Add agent message for this prompt
        agent_message = DiscoveryMessage(
            role="agent",
            content=current_prompt["question"],
            prompt_id=current_prompt["id"],
        ).model_dump()
        discovery_messages.append(agent_message)

        # Count prompts asked
        asked_count = sum(1 for p in discovery_prompts if p.get("asked", False))

        # Build interrupt payload
        interrupt_payload = {
            "interrupt_type": "discovery_prompt",
            "message": current_prompt["question"],
            "context": {
                "intent": current_prompt.get("intent", ""),
                "related_gaps": current_prompt.get("related_gaps", []),
                "prompt_number": asked_count,
                "total_prompts": len(discovery_prompts),
                "exchanges_completed": discovery_exchanges,
            },
            "can_skip": True,
        }

        # Return state with phase="waiting" - graph will loop back
        # This PERSISTS the state including messages before we call interrupt()
        logger.info(f"Discovery setup complete, asking prompt {asked_count}/{len(discovery_prompts)}")
        return {
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

        # Rebuild interrupt payload
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
            },
            "can_skip": True,
        }

        # Call interrupt to wait for user response
        user_response = interrupt(interrupt_payload)

        # Process user response
        result = await _handle_user_response(
            user_response,
            current_prompt,
            state,
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
) -> dict:
    """Handle user response to a discovery prompt.

    Now with adaptive questioning:
    - If LLM suggests a follow-up, insert it as next question
    - Follow-ups get higher priority than pre-generated questions
    - This creates a more natural conversation flow
    """
    discovery_messages = list(state.get("discovery_messages", []))
    discovered_experiences = list(state.get("discovered_experiences", []))
    discovery_exchanges = state.get("discovery_exchanges", 0)
    discovery_prompts = list(state.get("discovery_prompts", []))

    # Check for completion signals - skip all questions and go directly to draft
    if user_response.lower().strip() in ["done", "skip", "complete", "finish"]:
        return {
            "discovery_confirmed": True,
            "user_done_signal": True,  # Also skip QA phase
            "qa_complete": True,
            "current_step": "draft",  # Go directly to drafting
            "sub_step": None,
            "updated_at": datetime.now().isoformat(),
        }

    # Add user message
    user_message = DiscoveryMessage(
        role="user",
        content=user_response,
    ).model_dump()
    discovery_messages.append(user_message)

    # Process response
    result = await process_discovery_response(user_response, current_prompt, state)

    # Add extracted experiences
    new_experiences = result.get("extracted_experiences", [])
    if new_experiences:
        # Update user message with experience IDs
        user_message["experiences_extracted"] = [e["id"] for e in new_experiences]
        discovery_messages[-1] = user_message
        discovered_experiences.extend(new_experiences)

    # Increment exchange count
    discovery_exchanges += 1

    # Handle adaptive follow-up questions
    follow_up = result.get("follow_up")
    move_to_next = result.get("move_to_next", True)

    # If LLM suggested a follow-up and we shouldn't move on, insert it as next question
    if follow_up and not move_to_next and discovery_exchanges < 10:
        # Create a follow-up prompt with higher priority (lower number = higher priority)
        follow_up_prompt = {
            "id": f"followup_{uuid.uuid4().hex[:8]}",
            "question": follow_up,
            "intent": f"Follow up on: {current_prompt.get('intent', '')}",
            "related_gaps": current_prompt.get("related_gaps", []),
            "priority": 0,  # Highest priority - ask next
            "asked": False,
            "is_adaptive": True,  # Mark as dynamically generated
        }

        # Insert at the beginning so it's asked next
        discovery_prompts.insert(0, follow_up_prompt)
        logger.info(f"Inserted adaptive follow-up question: {follow_up[:50]}...")

    return {
        "discovery_prompts": discovery_prompts,
        "discovery_messages": discovery_messages,
        "discovered_experiences": discovered_experiences,
        "discovery_exchanges": discovery_exchanges,
        "updated_at": datetime.now().isoformat(),
    }
