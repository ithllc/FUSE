"""Mode-specific prompt templates for the two-pass vision pipeline."""

_MERMAID_OUTPUT_RULES = (
    "CRITICAL OUTPUT RULES:\n"
    "- Your response MUST begin with 'graph TD' or 'graph LR' (the Mermaid diagram declaration).\n"
    "- Output ONLY valid Mermaid.js code. No markdown code fences, no backticks, no commentary, no narrative.\n"
    "- Do NOT explain what you are doing. Do NOT include text like 'Refining...' or 'I'm now...'.\n"
    "- Node labels must NOT contain parentheses. Use square brackets for labels: NodeId[\"Label\"].\n"
    "- Use only alphanumeric characters and underscores for node IDs.\n"
)

WHITEBOARD_PROMPT = (
    "Focus exclusively on the whiteboard or sketch surface in this image. "
    "Ignore all people, hands, furniture, and background elements. "
    "Extract all boxes, labels, arrows, and connections visible on the writing surface. "
    "Preserve the spatial layout (left-to-right or top-to-bottom flow direction). "
    "{context_block}"
    + _MERMAID_OUTPUT_RULES
)

IMAGINE_PROMPT = (
    "The following physical objects have been assigned as architecture components:\n"
    "{proxy_registry}\n\n"
    "Identify these objects in the image. Determine their spatial relationships "
    "(proximity, grouping, pointing direction). "
    "Map the physical arrangement to the architecture they represent. "
    "{context_block}"
    + _MERMAID_OUTPUT_RULES
)

CHARADES_PROMPT = (
    "Analyze the person's hand gestures and body positioning in this image. "
    "Describe the spatial shape being formed (ring, star, hierarchy, pipeline, mesh, etc.). "
    "Recent voice context: {transcript_excerpt}\n"
    "{context_block}"
    "Cross-reference the gesture with the voice context to determine which topology or component is being described. "
    + _MERMAID_OUTPUT_RULES
)

GENERIC_FALLBACK_PROMPT = (
    "Analyze this image for any technical architecture content. "
    "Extract all components and relationships visible. "
    "{context_block}"
    + _MERMAID_OUTPUT_RULES
)


def build_context_block(current_mermaid: str = None) -> str:
    """Builds the incremental context block injected into all prompts."""
    if not current_mermaid:
        return ""
    return (
        "Current diagram state (update incrementally, do not regenerate from scratch):\n"
        f"```\n{current_mermaid}\n```\n"
    )
