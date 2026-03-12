"""Mode-specific prompt templates for the two-pass vision pipeline."""

WHITEBOARD_PROMPT = (
    "Focus exclusively on the whiteboard or sketch surface in this image. "
    "Ignore all people, hands, furniture, and background elements. "
    "Extract all boxes, labels, arrows, and connections visible on the writing surface. "
    "Preserve the spatial layout (left-to-right or top-to-bottom flow direction). "
    "{context_block}"
    "Output ONLY valid Mermaid.js 'graph TD' or 'graph LR' code. No markdown blocks or other text."
)

IMAGINE_PROMPT = (
    "The following physical objects have been assigned as architecture components:\n"
    "{proxy_registry}\n\n"
    "Identify these objects in the image. Determine their spatial relationships "
    "(proximity, grouping, pointing direction). "
    "Map the physical arrangement to the architecture they represent. "
    "{context_block}"
    "Output ONLY valid Mermaid.js 'graph TD' code reflecting the architecture. No markdown blocks or other text."
)

CHARADES_PROMPT = (
    "Analyze the person's hand gestures and body positioning in this image. "
    "Describe the spatial shape being formed (ring, star, hierarchy, pipeline, mesh, etc.). "
    "Recent voice context: {transcript_excerpt}\n"
    "{context_block}"
    "Cross-reference the gesture with the voice context to determine which topology or component is being described. "
    "Output ONLY valid Mermaid.js 'graph TD' code. No markdown blocks or other text."
)

GENERIC_FALLBACK_PROMPT = (
    "Analyze this image for any technical architecture content. "
    "Extract all components and relationships visible. "
    "{context_block}"
    "Output ONLY valid Mermaid.js 'graph TD' code. No markdown blocks or other text."
)


def build_context_block(current_mermaid: str = None) -> str:
    """Builds the incremental context block injected into all prompts."""
    if not current_mermaid:
        return ""
    return (
        "Current diagram state (update incrementally, do not regenerate from scratch):\n"
        f"```\n{current_mermaid}\n```\n"
    )
