from typing import Dict, Any, List
from google import genai
from google.genai import types

class ProofOrchestrator:
    """
    Pipes the architectural state into a proof orchestrator using Gemini 3.1 Pro
    for complex technical reasoning and session-level validation.
    """
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.client = genai.Client(vertexai=True, project=project_id, location=location)
        self.model_id = "gemini-3.1-pro"

    def validate_architecture(self, mermaid_code: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validates the current architectural state against technical constraints.
        """
        prompt = (
            f"Review the following Mermaid.js architectural model:\n\n{mermaid_code}\n\n"
            f"History of session events: {history}\n\n"
            "Identify any logical inconsistencies, network bottlenecks, or single points of failure. "
            "If the design is invalid, state the reason clearly. If valid, provide a succinct "
            "Feasibility Report."
        )

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                )
            ]
        )

        return {
            "validation_report": response.text,
            "is_valid": "INVALID" not in response.text.upper()
        }

if __name__ == "__main__":
    # po = ProofOrchestrator(project_id="fuse-489616")
    # result = po.validate_architecture("graph LR; A-->B;", [])
    # print(result["validation_report"])
    pass
