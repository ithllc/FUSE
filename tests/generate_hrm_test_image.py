"""Generate a test image with 6 shapes representing the Hierarchical Reasoning Model architecture.

Based on the ARGOS feasibility report:
- HRM Core (central hexagon)
- High-Level Module f_H (rectangle, top)
- Low-Level Module f_L (rectangle, bottom)
- Multimodal Fusion (oval, left)
- Agent Coordinator (diamond, right)
- Sensory Agents (rounded rect, bottom-right)

Shapes are connected with arrows showing data flow.
"""
from PIL import Image, ImageDraw, ImageFont
import os

WIDTH, HEIGHT = 800, 600
BG = (255, 255, 255)
OUTLINE = (40, 40, 40)
COLORS = {
    "hrm":     (100, 149, 237),  # cornflower blue
    "high":    (144, 238, 144),  # light green
    "low":     (255, 182, 108),  # light orange
    "fusion":  (221, 160, 221),  # plum
    "coord":   (255, 215, 0),    # gold
    "sensory": (135, 206, 235),  # sky blue
}

def draw_hexagon(draw, cx, cy, r, fill, outline):
    import math
    pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
           for a in range(0, 360, 60)]
    draw.polygon(pts, fill=fill, outline=outline, width=2)

def draw_diamond(draw, cx, cy, w, h, fill, outline):
    pts = [(cx, cy - h), (cx + w, cy), (cx, cy + h), (cx - w, cy)]
    draw.polygon(pts, fill=fill, outline=outline, width=2)

def text_center(draw, x, y, text, font, fill=(0, 0, 0)):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x - tw / 2, y - th / 2), text, fill=fill, font=font)

def draw_arrow(draw, x1, y1, x2, y2, fill=(80, 80, 80), width=2):
    draw.line([(x1, y1), (x2, y2)], fill=fill, width=width)
    # arrowhead
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    al = 12
    for da in [2.7, -2.7]:
        ax = x2 - al * math.cos(angle + da)
        ay = y2 - al * math.sin(angle + da)
        draw.line([(x2, y2), (ax, ay)], fill=fill, width=width)

def generate():
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        sfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
        sfont = font

    # Title
    text_center(draw, 400, 25, "Hierarchical Reasoning Model (HRM) Architecture", font, (40, 40, 40))

    # 1. HRM Core — hexagon (center)
    draw_hexagon(draw, 400, 260, 65, COLORS["hrm"], OUTLINE)
    text_center(draw, 400, 252, "HRM Core", font)
    text_center(draw, 400, 272, "(Dual-Process)", sfont)

    # 2. High-Level Module f_H — rectangle (top center)
    draw.rounded_rectangle([310, 80, 490, 140], radius=8, fill=COLORS["high"], outline=OUTLINE, width=2)
    text_center(draw, 400, 100, "High-Level Module", font)
    text_center(draw, 400, 120, "f_H (Slow Reasoning)", sfont)

    # 3. Low-Level Module f_L — rectangle (bottom center)
    draw.rounded_rectangle([310, 380, 490, 440], radius=8, fill=COLORS["low"], outline=OUTLINE, width=2)
    text_center(draw, 400, 400, "Low-Level Module", font)
    text_center(draw, 400, 420, "f_L (Fast Perception)", sfont)

    # 4. Multimodal Fusion — ellipse (left)
    draw.ellipse([70, 220, 250, 300], fill=COLORS["fusion"], outline=OUTLINE, width=2)
    text_center(draw, 160, 252, "Multimodal", font)
    text_center(draw, 160, 272, "Fusion", sfont)

    # 5. Agent Coordinator — diamond (right)
    draw_diamond(draw, 620, 260, 80, 50, COLORS["coord"], OUTLINE)
    text_center(draw, 620, 252, "Agent", font)
    text_center(draw, 620, 272, "Coordinator", sfont)

    # 6. Sensory Agents — rounded rect (bottom right)
    draw.rounded_rectangle([540, 400, 710, 470], radius=15, fill=COLORS["sensory"], outline=OUTLINE, width=2)
    text_center(draw, 625, 422, "Sensory Agents", font)
    text_center(draw, 625, 442, "(RL-based)", sfont)

    # Arrows: data flow connections
    draw_arrow(draw, 400, 140, 400, 195)   # f_H -> HRM Core
    draw_arrow(draw, 400, 325, 400, 380)   # HRM Core -> f_L
    draw_arrow(draw, 250, 260, 335, 260)   # Fusion -> HRM Core
    draw_arrow(draw, 465, 260, 540, 260)   # HRM Core -> Coordinator
    draw_arrow(draw, 620, 310, 625, 400)   # Coordinator -> Sensory Agents
    draw_arrow(draw, 540, 435, 490, 420)   # Sensory Agents -> f_L (feedback)

    # Legend
    draw.rectangle([20, 510, 780, 590], fill=(248, 248, 248), outline=(200, 200, 200))
    text_center(draw, 400, 525, "Data Flow: Fusion → HRM Core ↔ f_H/f_L → Coordinator → Sensory Agents → Feedback Loop", sfont)
    text_center(draw, 400, 545, "Based on: ARGOS Feasibility Report — HRM with Dual-Process Cognitive Coordination", sfont)
    text_center(draw, 400, 565, "6 Components | Hierarchical Multi-Tier Topology | DEQ-based Training", sfont)

    out_path = os.path.join(os.path.dirname(__file__), "hrm_architecture_test.jpg")
    img.save(out_path, "JPEG", quality=90)
    print(f"Test image saved to {out_path}")
    return out_path

if __name__ == "__main__":
    generate()
