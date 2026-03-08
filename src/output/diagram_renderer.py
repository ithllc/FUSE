import subprocess
import os
import tempfile
from typing import Optional

class DiagramRenderer:
    """
    Renders Mermaid.js code into high-fidelity diagrams using the Mermaid CLI (mmdc).
    """
    def __init__(self, output_dir: str = "output/diagrams"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def render(self, mermaid_code: str, filename: str = "latest_architecture.png") -> Optional[str]:
        """
        Converts Mermaid code to a PNG image.
        """
        if not mermaid_code:
            print("Error: No Mermaid code provided for rendering.")
            return None

        # Create a temporary file for the Mermaid code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as tmp:
            tmp.write(mermaid_code)
            tmp_path = tmp.name

        output_path = os.path.join(self.output_dir, filename)
        
        try:
            # Execute mmdc command
            # Note: --puppeteerConfigFile may be needed in some Docker environments
            result = subprocess.run(
                ["mmdc", "-i", tmp_path, "-o", output_path, "-t", "forest", "-b", "white"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"Diagram successfully rendered to {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"Mermaid rendering error: {e.stderr}")
            return None
        finally:
            # Clean up the temporary Mermaid file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == "__main__":
    # Example usage:
    # renderer = DiagramRenderer()
    # renderer.render("graph TD; A-->B;")
    pass
