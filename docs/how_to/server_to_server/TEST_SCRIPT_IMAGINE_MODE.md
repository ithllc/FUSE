# Test Script: Imagine Mode (Proxy Objects)

**Purpose**: End-to-end test of FUSE using physical objects as stand-ins for architecture components.
**Duration**: ~5 minutes
**What you need**: 3-4 everyday objects on a table (e.g., stapler, coffee mug, phone, pen, book)

---

## Setup

1. Open https://fuse-service-864533297567.us-central1.run.app in Chrome
2. Wait for the splash page countdown to finish
3. Place 3-4 objects on a table or desk in front of your camera:
   - **Stapler** (will be the Load Balancer)
   - **Coffee mug** (will be the Database)
   - **Phone** (will be the API Gateway)
   - **Pen** (will be the Cache Layer)

---

## Phase 1: Pre-Session Diagnostics

1. Click **"Start Session"**
   - _Expected_: Camera and microphone activate, countdown starts

2. When prompted, say: **"Hello FUSE"**
   - _Expected_: All 3 diagnostics pass (Mic, Audio Output, Camera)
   - _Expected_: "Session active" appears in connection log

_(If any diagnostic fails, see troubleshooting in the Whiteboard Mode script)_

---

## Phase 2: Switch to Imagine Mode

3. Say:
   > **"Switch to imagine mode"**
   - _Expected_: FUSE responds: "Switched to imagine mode"
   - _Expected_: Vision mode dropdown shows "Imagine (Objects)"

---

## Phase 3: Register Proxy Objects

Register each physical object as an architecture component. Speak clearly and pause between each assignment.

4. Hold up the stapler and say:
   > **"This stapler is our load balancer"**
   - _Expected_: Connection log shows "TOOL: set_proxy_object ✓"
   - _Expected_: FUSE responds: "Understood. The stapler is now the load balancer."
   - _Expected_: Proxy Objects tab updates with: stapler → load balancer

5. Hold up the coffee mug and say:
   > **"This coffee mug is our primary database"**
   - _Expected_: Connection log shows "TOOL: set_proxy_object ✓"
   - _Expected_: FUSE acknowledges the assignment

6. Hold up the phone and say:
   > **"This phone is the API gateway"**
   - _Expected_: Another "TOOL: set_proxy_object ✓" in the log

7. Hold up the pen and say:
   > **"This pen is the cache layer"**
   - _Expected_: Fourth proxy registered

8. Verify all proxies by asking:
   > **"What objects have been assigned so far?"**
   - _Expected_: Connection log shows "TOOL: get_session_context ✓"
   - _Expected_: FUSE lists all 4 proxy assignments via audio

---

## Phase 4: Spatial Architecture with Function Calling

Now arrange the objects to represent your architecture and ask FUSE to analyze the layout.

9. Arrange the objects on the table:
   - Phone (API Gateway) on the left
   - Stapler (Load Balancer) in the middle
   - Coffee mug (Database) and Pen (Cache) on the right side

10. Point the camera at the arrangement and say:
    > **"FUSE, look at the table. Can you see how the objects are arranged and describe the architecture?"**
    - _Expected_: Connection log shows "TOOL: capture_and_analyze_frame ✓"
    - _Expected_: FUSE describes the spatial layout: "I can see the API gateway on the left, connecting through the load balancer in the center, which routes to the database and cache on the right..."
    - _Expected_: Diagram panel updates with a Mermaid diagram reflecting the arrangement

11. Ask for refinement:
    > **"The API gateway should connect to the load balancer, and the load balancer should connect to both the database and the cache. The cache sits in front of the database."**
    - _Expected_: FUSE acknowledges and the vision pipeline captures the relationship context
    - _Expected_: Diagram updates with the correct topology

12. Move an object and describe the change:
    > **"I'm moving the cache next to the database. The cache should sit between the load balancer and the database."**
    - _Expected_: FUSE acknowledges the topology change

---

## Phase 5: Architecture Validation

13. Ask verbally:
    > **"Validate this architecture. Does it have any bottlenecks or single points of failure?"**
    - _Expected_: FUSE discusses potential issues
    - _Expected_: Example: "The load balancer is a single point of failure. Consider adding a secondary load balancer for redundancy."

14. Or click **"Run Validation"** in the bottom-right panel
    - _Expected_: Written validation report with specific findings

---

## Phase 6: Visualization (Imagen)

15. Click **"Visualize"** in the diagram panel
    - _Expected_: Photorealistic image generates (10-30 seconds)
    - _Expected_: You see visual metaphors for each component:
      - Load balancer → traffic control structure
      - Database → vault with data streams
      - API gateway → ornate gateway arch
      - Cache → high-speed relay station

---

## Phase 7: Animation (Veo 3)

16. Click **"Animate"** in the diagram panel
    - _Expected_: Animated walkthrough generates (30-120 seconds)
    - _Expected_: Video shows data flowing through the architecture components

---

## Phase 8: End Session

17. Click **"End Session"**
    - _Expected_: "WebSocket closed: Normal closure" (code 1000)
    - _Expected_: Post-session overlay with session summary

---

## What to Check in the Connection Log

| Entry | Meaning |
|-------|---------|
| `TOOL: set_proxy_object ✓ (XXXms)` | Proxy registered via function call |
| `TOOL: capture_and_analyze_frame ✓ (XXXms)` | Vision captured objects on demand |
| `TOOL: get_session_context ✓ (XXXms)` | Session state retrieved |
| `Audio session reconnected` | Auto-reconnect worked (issue #18) |

## What to Check in the Proxy Objects Tab

After all registrations, you should see:

| Object | Technical Role |
|--------|---------------|
| stapler | load balancer |
| coffee mug | primary database |
| phone | API gateway |
| pen | cache layer |
