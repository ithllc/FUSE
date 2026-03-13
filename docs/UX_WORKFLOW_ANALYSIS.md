# UX Analysis: Automated Workflow Progression with Status Tabs

## Problem Statement

The current UI requires the user to manually click **Visualize**, **Animate**, and **Validate** buttons to progress through the workflow. There is no visibility into what the system is doing, and the outputs (realistic image, animation video) are hidden behind a toggle view that shares space with the diagram. This creates:

1. **No trust signal** — The user doesn't know if the system is working or stuck
2. **Hidden outputs** — Generated images/videos are stuffed into a toggle view, easy to miss
3. **Manual button-press dependency** — Every workflow step requires user intervention
4. **No progressive disclosure** — All buttons are enabled regardless of whether prerequisites are met

## Proposed Solution

### 1. Add Dedicated Tabs: "Visualized Image" and "Animated Video"

**Current tabs:** `Architecture Diagram` | `Validation`

**New tabs:** `Architecture Diagram` | `Validation` | `Visualized Image` | `Animated Video`

**Behavior:**
- `Visualized Image` and `Animated Video` tabs start **disabled** (grayed out, not clickable)
- When Imagen finishes generating, the `Visualized Image` tab activates with a subtle glow/pulse
- When Veo3 finishes generating, the `Animated Video` tab activates similarly
- Each tab shows its content independently — no more toggle view sharing space with the diagram

### 2. Connection Log Status Updates for Each Workflow Step

Every workflow stage should log its progress to the connection log:

| Event | Log Entry |
|-------|-----------|
| Diagram created | `WORKFLOW: Architecture diagram generated (342 chars)` |
| Validation started | `WORKFLOW: Validating architecture...` |
| Validation complete | `WORKFLOW: Validation complete — 3 issues found` |
| Imagen started | `WORKFLOW: Generating photorealistic image (Imagen 4.0)...` |
| Imagen complete | `WORKFLOW: Image generated (1.5 MB) ✓` |
| Veo3 started | `WORKFLOW: Generating animated walkthrough (Veo 3.0)...` |
| Veo3 complete | `WORKFLOW: Animation generated (2.1 MB, 6s) ✓` |
| Any failure | `WORKFLOW: [step] failed — [reason]` |

### 3. Auto-Trigger Workflow After Diagram Creation

When a diagram is created/updated (via vision frame or voice), automatically kick off:

```
Diagram created → Auto-validate → Auto-visualize (Imagen) → Auto-animate (Veo3)
```

Each step runs in sequence. The user sees real-time progress in the connection log and tabs activate as each step completes. Buttons remain available for manual re-trigger.

### 4. Tab Activation States

| Tab | Initial State | Activates When |
|-----|---------------|----------------|
| Architecture Diagram | Active (default) | Always available |
| Validation | Enabled but empty | Validation completes |
| Visualized Image | **Disabled** | Imagen returns image |
| Animated Video | **Disabled** | Veo3 returns video |

### 5. Visual Indicators

- **Disabled tab**: `opacity: 0.4; cursor: not-allowed; pointer-events: none`
- **Processing tab**: Spinner icon next to tab name, `opacity: 0.7`
- **Ready tab**: Subtle pulse/glow animation on first activation, then normal style
- **Active tab**: Standard active style (green underline)

## Implementation Plan

### HTML Changes (static/index.html)

1. Add two new tab divs after Validation:
   ```html
   <div class="tab disabled" id="tabVisualizedImage" onclick="switchArchTab('visualized')">Visualized Image</div>
   <div class="tab disabled" id="tabAnimatedVideo" onclick="switchArchTab('animated')">Animated Video</div>
   ```

2. Add two new tab-content divs:
   ```html
   <div class="tab-content" id="arch-visualized">
       <img id="visualizedImage" style="max-width:100%; border-radius:8px;" />
       <div id="visualizedProgress">...</div>
   </div>
   <div class="tab-content" id="arch-animated">
       <video id="animatedVideo" controls style="max-width:100%; border-radius:8px;"></video>
       <div id="animatedProgress">...</div>
   </div>
   ```

### CSS Changes

```css
.tab.disabled { opacity: 0.4; cursor: not-allowed; pointer-events: none; }
.tab.processing { opacity: 0.7; }
.tab.processing::after { content: '...'; animation: pulse 1s infinite; }
.tab.ready { animation: tab-glow 2s ease-out; }
@keyframes tab-glow { 0% { box-shadow: 0 0 8px rgba(88,166,255,0.6); } 100% { box-shadow: none; } }
```

### JavaScript Changes

1. `activateTab(tabId)` — removes `disabled` class, adds `ready` class temporarily
2. `setTabProcessing(tabId)` — adds `processing` class
3. Modify `generateRealistic()` to:
   - Set `tabVisualizedImage` to processing
   - Log `WORKFLOW: Generating...` to connection log
   - On success: place image in `arch-visualized`, activate tab, log completion
4. Modify `generateAnimation()` — same pattern for video tab
5. Add `autoWorkflow()` — triggered after diagram update, chains validate → visualize → animate

### Server-Side Changes

None required — the existing endpoints (`/render/realistic`, `/render/animate`, `/validate`) already return the right data. The auto-trigger is client-side.

## Trust-Building UX Pattern

The key insight: **show progress, show results, show them separately.**

```
User starts session
  → Talks to FUSE about architecture
    → Diagram tab updates in real-time
      → Connection log: "WORKFLOW: Validating..."
        → Validation tab activates ✓
          → Connection log: "WORKFLOW: Generating image..."
            → Visualized Image tab activates ✓
              → Connection log: "WORKFLOW: Generating animation..."
                → Animated Video tab activates ✓
```

Each tab is a "completed milestone" the user can inspect at any time. No buttons needed for the happy path — they see the system working autonomously and can review each artifact independently.
