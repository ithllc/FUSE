"""Converts Mermaid.js diagram code into natural-language scene descriptions
for photorealistic image generation prompts."""

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("fuse.translator")


# --- Node Type to Visual Metaphor Mapping ---

NODE_VISUAL_MAP: Dict[str, str] = {
    # Infrastructure
    "server":        "a sleek rack-mounted server with blue LED status lights",
    "database":      "a cylindrical database storage unit with glowing data rings",
    "db":            "a cylindrical database storage unit with glowing data rings",
    "cache":         "a translucent high-speed memory module radiating warm light",
    "redis":         "a translucent high-speed memory module with a red-orange glow",
    "queue":         "a conveyor-belt pipeline with glowing data packets in transit",
    "kafka":         "a high-throughput streaming pipeline with parallel data lanes",
    "load_balancer": "a traffic control tower distributing beams of light to servers below",
    "lb":            "a traffic control tower distributing beams of light to servers below",
    "api":           "a gateway portal with a shimmering data membrane",
    "gateway":       "a fortified gateway arch with scanning beams",
    "cdn":           "a network of satellite relay nodes orbiting a central hub",
    "dns":           "a directory beacon tower broadcasting address signals",
    "firewall":      "a translucent energy shield wall with filtering patterns",
    "proxy":         "an intermediary relay station with routing indicators",
    "storage":       "a massive data vault with layered storage drawers",
    "s3":            "a cloud storage array floating with holographic access points",
    "blob":          "a cloud storage array floating with holographic access points",

    # Compute
    "gpu":           "a high-performance computing blade with heat-sink fins glowing orange",
    "cpu":           "a processing core with circuit-trace patterns pulsing with data",
    "container":     "a modular shipping-container-like compute pod",
    "docker":        "a modular blue compute container with the whale insignia",
    "kubernetes":    "an orchestration control deck managing rows of container pods",
    "k8s":           "an orchestration control deck managing rows of container pods",
    "lambda":        "a serverless execution orb that materializes on demand",
    "function":      "a serverless execution orb that materializes on demand",
    "vm":            "a virtual machine enclosure with a semitransparent shell",
    "worker":        "an industrial processing unit with conveyor input/output",

    # Application
    "frontend":      "a glass-panel user interface screen floating in space",
    "ui":            "a glass-panel user interface screen floating in space",
    "client":        "a user workstation with a holographic display",
    "browser":       "a browser window frame hovering above a user desk",
    "mobile":        "a smartphone device with an active touch interface",
    "backend":       "a server rack cluster behind a secure partition",
    "microservice":  "a small self-contained service pod with an API connector port",
    "service":       "a modular service unit with input/output connection ports",
    "auth":          "a biometric security checkpoint with scanning beams",
    "ml":            "a neural network processor with layered glowing nodes",
    "ai":            "an AI inference engine with radiating neural pathways",
    "model":         "a neural network processor with layered glowing nodes",
    "analytics":     "a data observatory dome with live dashboard projections",
    "monitoring":    "a surveillance command center with wall-mounted metric displays",
    "logging":       "a scrolling data recorder with continuous tape output",

    # External
    "user":          "a holographic user silhouette interacting with the system",
    "external":      "a distant system represented as a floating remote node",
    "third_party":   "a partner system module docked at the system boundary",
    "internet":      "a vast interconnected web of light filaments representing the global network",
}

# --- Relationship Type to Visual Connection Mapping ---

EDGE_VISUAL_MAP: Dict[str, str] = {
    "-->":   "connected by a glowing fiber-optic data stream flowing",
    "---":   "linked by a steady structural beam",
    "-.->":  "connected by a pulsing dashed energy trail flowing",
    "==>":   "joined by a thick high-bandwidth conduit carrying heavy data",
    "--o":   "attached via a monitoring probe",
    "--x":   "blocked by a terminated connection barrier",
    "o--o":  "sharing a bidirectional sync link",
}


class MermaidSceneTranslator:
    """Converts Mermaid.js diagram code into a natural-language scene
    description suitable for photorealistic image generation prompts."""

    def __init__(self, node_map: Dict[str, str] = None, edge_map: Dict[str, str] = None):
        self.node_map = node_map or NODE_VISUAL_MAP
        self.edge_map = edge_map or EDGE_VISUAL_MAP

    def _extract_nodes(self, mermaid_code: str) -> Dict[str, str]:
        """Extract node IDs and their labels from Mermaid code."""
        nodes: Dict[str, str] = {}

        patterns = [
            r'(\w+)\[([^\]]+)\]',       # square brackets
            r'(\w+)\(([^)]+)\)',         # parentheses
            r'(\w+)\{([^}]+)\}',         # curly braces
            r'(\w+)\(\(([^)]+)\)\)',      # double parens
            r'(\w+)\[\[([^\]]+)\]\]',    # double brackets
            r'(\w+)\[/([^\]]+)/\]',      # trapezoid
            r'(\w+)>\s*([^\]]+)\]',      # asymmetric
        ]

        reserved = {"graph", "flowchart", "subgraph", "end", "style", "classDef"}

        for pattern in patterns:
            for match in re.finditer(pattern, mermaid_code):
                node_id = match.group(1).strip()
                label = match.group(2).strip()
                if node_id not in reserved:
                    nodes[node_id] = label

        # Catch bare node IDs used in edges but not defined with labels
        edge_nodes = re.findall(r'(\w+)\s*(?:-->|---|-\.->|==>|--o|--x|o--o)', mermaid_code)
        edge_nodes += re.findall(r'(?:-->|---|-\.->|==>|--o|--x|o--o)\s*(\w+)', mermaid_code)
        for nid in edge_nodes:
            nid = nid.strip()
            if nid not in nodes and nid not in reserved:
                nodes[nid] = nid

        return nodes

    def _extract_edges(self, mermaid_code: str) -> List[Tuple[str, str, str, str]]:
        """Extract edges. Returns list of (source, edge_type, target, label)."""
        edges: List[Tuple[str, str, str, str]] = []

        pattern = r'(\w+)\s*(-->|---|-\.->|==>|--o|--x|o--o)\s*(?:\|([^|]*)\|\s*)?(\w+)'
        for match in re.finditer(pattern, mermaid_code):
            source = match.group(1).strip()
            edge_type = match.group(2).strip()
            label = (match.group(3) or "").strip()
            target = match.group(4).strip()
            edges.append((source, edge_type, target, label))

        return edges

    def _extract_subgraphs(self, mermaid_code: str) -> List[Tuple[str, List[str]]]:
        """Extract subgraph groupings."""
        subgraphs: List[Tuple[str, List[str]]] = []

        sg_pattern = r'subgraph\s+(.+?)(?:\n|\r)(.*?)end'
        for match in re.finditer(sg_pattern, mermaid_code, re.DOTALL):
            label = match.group(1).strip().strip('"').strip("'")
            body = match.group(2)
            body_nodes = re.findall(r'(\w+)(?:\[|\(|\{|-->|---)', body)
            subgraphs.append((label, body_nodes))

        return subgraphs

    def _match_visual(self, label: str) -> str:
        """Match a node label to the best visual metaphor."""
        label_lower = label.lower().replace(" ", "_").replace("-", "_")

        # Direct match
        if label_lower in self.node_map:
            return self.node_map[label_lower]

        # Partial match
        for key, visual in self.node_map.items():
            if key in label_lower:
                return visual

        # Generic fallback
        return f"a technical component labeled '{label}' with indicator lights and data ports"

    def translate(self, mermaid_code: str) -> str:
        """Translate full Mermaid.js code into a scene description string."""
        nodes = self._extract_nodes(mermaid_code)
        edges = self._extract_edges(mermaid_code)
        subgraphs = self._extract_subgraphs(mermaid_code)

        scene_parts: List[str] = []

        node_count = len(nodes)
        scene_parts.append(
            f"A sprawling modern technology infrastructure with {node_count} "
            f"distinct components arranged in an organized layout."
        )

        for sg_label, sg_nodes in subgraphs:
            zone_desc = (
                f"A clearly delineated zone labeled '{sg_label}' "
                f"containing {len(sg_nodes)} components, "
                f"enclosed by a subtle boundary glow."
            )
            scene_parts.append(zone_desc)

        for node_id, label in nodes.items():
            visual = self._match_visual(label)
            scene_parts.append(f"Component '{label}' represented as {visual}.")

        for source, edge_type, target, label in edges:
            source_label = nodes.get(source, source)
            target_label = nodes.get(target, target)
            edge_visual = self.edge_map.get(edge_type, "connected by a data link")

            edge_desc = f"'{source_label}' is {edge_visual} to '{target_label}'"
            if label:
                edge_desc += f" carrying '{label}' data"
            edge_desc += "."
            scene_parts.append(edge_desc)

        return " ".join(scene_parts)
