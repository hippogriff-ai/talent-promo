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

    prompt = f"""You are a career coach helping {user_name} prepare for an application to {job_title} at {company_name}.

Based on the gap analysis, generate discovery questions to surface hidden or forgotten experiences that could address the candidate's gaps.

## Gap Analysis
Gaps to address:
{chr(10).join(f"- {g}" for g in gaps[:5])}

Opportunities to explore:
{chr(10).join(f"- {o.get('description', o) if isinstance(o, dict) else o}" for o in opportunities[:3])}

## Job Requirements
{chr(10).join(f"- {r}" for r in requirements[:5])}

## Candidate's Known Experience
{experience_summary}

## Instructions
Generate 5-7 discovery questions that:
1. Are open-ended and encourage detailed responses
2. Target specific gaps or requirements
3. Help surface experiences the candidate may have forgotten or undervalued
4. Are ordered by priority (most important gaps first)

For each question, provide:
- The question itself
- The intent (what you're trying to uncover)
- Which gaps it relates to

Output as JSON array:
[
  {{
    "question": "Can you think of a time when you had to learn a new technology quickly to complete a project?",
    "intent": "Uncover rapid learning ability and adaptability",
    "related_gaps": ["Limited experience with cloud infrastructure"],
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
    """Generate fallback prompts if LLM fails."""
    fallback_questions = [
        {
            "question": "Can you describe a project where you had to learn something completely new to succeed?",
            "intent": "Uncover adaptability and learning ability",
            "related_gaps": gaps[:1] if gaps else [],
            "priority": 1,
        },
        {
            "question": "Tell me about a time you led a team or initiative, even informally.",
            "intent": "Surface leadership experience",
            "related_gaps": gaps[1:2] if len(gaps) > 1 else [],
            "priority": 2,
        },
        {
            "question": "What's a challenging problem you solved that you're particularly proud of?",
            "intent": "Identify problem-solving achievements",
            "related_gaps": gaps[2:3] if len(gaps) > 2 else [],
            "priority": 3,
        },
        {
            "question": "Have you ever worked with stakeholders from different departments or backgrounds?",
            "intent": "Uncover cross-functional collaboration",
            "related_gaps": gaps[3:4] if len(gaps) > 3 else [],
            "priority": 4,
        },
        {
            "question": "What side projects, volunteer work, or personal interests demonstrate skills relevant to this role?",
            "intent": "Surface non-work experiences that show capability",
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

    prompt = f"""You are analyzing a user's response during a career discovery conversation.

## Context
Original question: {current_prompt.get('question', '')}
Question intent: {current_prompt.get('intent', '')}
Related gaps: {', '.join(current_prompt.get('related_gaps', []))}

## Job Requirements
{chr(10).join(f"- {r}" for r in requirements[:5])}

## User's Response
{user_response}

## Instructions
Analyze the response and:
1. Identify any concrete experiences or achievements mentioned
2. Determine if a follow-up question would help get more detail
3. Map experiences to specific job requirements

For each experience found, extract:
- A clear description
- The exact quote that reveals it
- Which job requirements it addresses

Output as JSON:
{{
  "experiences": [
    {{
      "description": "Led migration of legacy system to cloud",
      "source_quote": "I actually led our team's move to AWS when our old servers...",
      "mapped_requirements": ["Cloud infrastructure experience", "Technical leadership"]
    }}
  ],
  "follow_up": "Can you tell me more about the specific challenges you faced during that migration?",
  "move_to_next": false
}}

If no experiences were found or response was too brief, set experiences to empty array and suggest a follow-up.
If the response was comprehensive, set move_to_next to true.
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

    This node:
    1. On first entry: generates discovery prompts from gap analysis
    2. Returns the first prompt via interrupt for user response
    3. On resume: processes user response and returns next prompt or completes
    """
    from langgraph.types import interrupt

    discovery_prompts = state.get("discovery_prompts", [])
    discovery_messages = state.get("discovery_messages", [])
    discovered_experiences = state.get("discovered_experiences", [])
    discovery_exchanges = state.get("discovery_exchanges", 0)
    discovery_confirmed = state.get("discovery_confirmed", False)

    # Check if discovery is already confirmed
    if discovery_confirmed:
        logger.info("Discovery already confirmed, proceeding to next step")
        return {
            "current_step": "qa",
            "updated_at": datetime.now().isoformat(),
        }

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

        # Get first prompt
        first_prompt = prompts[0]
        first_prompt["asked"] = True

        # Add agent message
        agent_message = DiscoveryMessage(
            role="agent",
            content=first_prompt["question"],
            prompt_id=first_prompt["id"],
        ).model_dump()

        # Build interrupt payload
        interrupt_payload = {
            "interrupt_type": "discovery_prompt",
            "message": first_prompt["question"],
            "context": {
                "intent": first_prompt.get("intent", ""),
                "related_gaps": first_prompt.get("related_gaps", []),
                "prompt_number": 1,
                "total_prompts": len(prompts),
            },
            "can_skip": True,
        }

        # Save state before interrupt
        new_state = {
            "discovery_prompts": prompts,
            "discovery_messages": [agent_message],
            "current_step": "discovery",
            "sub_step": "awaiting_response",
            "pending_interrupt": interrupt_payload,
            "updated_at": datetime.now().isoformat(),
        }

        # Interrupt for user response
        user_response = interrupt(interrupt_payload)

        # Process user response
        return await _handle_user_response(
            user_response,
            first_prompt,
            {**state, **new_state},
        )

    # Get next prompt
    next_prompt = get_next_prompt(state)

    if not next_prompt:
        # All prompts asked, complete discovery
        logger.info("All discovery prompts asked")
        return {
            "discovery_confirmed": True,
            "current_step": "qa",
            "sub_step": None,
            "updated_at": datetime.now().isoformat(),
        }

    # Mark prompt as asked
    prompts = state.get("discovery_prompts", [])
    for p in prompts:
        if p["id"] == next_prompt["id"]:
            p["asked"] = True
            break

    # Add agent message
    agent_message = DiscoveryMessage(
        role="agent",
        content=next_prompt["question"],
        prompt_id=next_prompt["id"],
    ).model_dump()

    messages = list(discovery_messages)
    messages.append(agent_message)

    # Count prompts asked
    asked_count = sum(1 for p in prompts if p.get("asked", False))

    # Build interrupt payload
    interrupt_payload = {
        "interrupt_type": "discovery_prompt",
        "message": next_prompt["question"],
        "context": {
            "intent": next_prompt.get("intent", ""),
            "related_gaps": next_prompt.get("related_gaps", []),
            "prompt_number": asked_count,
            "total_prompts": len(prompts),
        },
        "can_skip": True,
    }

    # Interrupt for user response
    user_response = interrupt(interrupt_payload)

    # Process user response
    return await _handle_user_response(
        user_response,
        next_prompt,
        {
            **state,
            "discovery_prompts": prompts,
            "discovery_messages": messages,
        },
    )


async def _handle_user_response(
    user_response: str,
    current_prompt: dict,
    state: ResumeState,
) -> dict:
    """Handle user response to a discovery prompt."""
    discovery_messages = list(state.get("discovery_messages", []))
    discovered_experiences = list(state.get("discovered_experiences", []))
    discovery_exchanges = state.get("discovery_exchanges", 0)

    # Check for completion signals
    if user_response.lower().strip() in ["done", "skip", "complete", "finish"]:
        return {
            "discovery_confirmed": True,
            "current_step": "qa",
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

    # Check if follow-up needed
    follow_up = result.get("follow_up")
    move_to_next = result.get("move_to_next", True)

    # For now, always move to next prompt (simplified flow)
    # Could be enhanced to handle follow-ups

    return {
        "discovery_messages": discovery_messages,
        "discovered_experiences": discovered_experiences,
        "discovery_exchanges": discovery_exchanges,
        "updated_at": datetime.now().isoformat(),
    }
