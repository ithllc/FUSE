# Test Script: Imagine Mode (Ephemeral Tokens)

**Purpose**: End-to-end test of FUSE proxy object assignment using physical objects as architecture components.
**Duration**: ~5 minutes
**What you need**: 2-3 everyday objects on your desk (cup, phone, pen, stapler, etc.)

---

## Setup

1. Open https://fuse-service-864533297567.us-central1.run.app in Chrome
2. Click "Ready — Enter FUSE" after the splash page loads
3. Wait for components to load, then click **Start Session**
4. Grant mic and camera permissions if prompted
5. Wait for FUSE to greet you (~10 seconds)
6. Place 2-3 objects on your desk in view of the camera

---

## Step 1: Introduce Objects as Proxies

1. Point the camera at your objects
2. Say: **"Look at the objects on my desk. The cup is our database and the phone is the API gateway."**
3. Watch for in the chat panel:
   - `TOOL CALL: capture_and_analyze_frame({"mode":"imagine"})` — Gemini captures what it sees
   - `TOOL CALL: set_proxy_object({"object_name":"cup","technical_role":"database"})` — registers the cup
   - `TOOL CALL: set_proxy_object({"object_name":"phone","technical_role":"API gateway"})` — registers the phone
4. Check the **Session Notes** tab → **Proxy Objects** sub-tab — cup and phone should appear in the table

---

## Step 2: Add More Proxies

1. Pick up another object (e.g., a pen)
2. Say: **"And this pen is our message queue between the API gateway and the database."**
3. Watch for:
   - `TOOL CALL: set_proxy_object({"object_name":"pen","technical_role":"message queue"})`
4. The proxy table updates with the new assignment

---

## Step 3: Ask About Context

1. Say: **"What objects have we assigned so far? And what does our current architecture look like?"**
2. Watch for:
   - `TOOL CALL: get_session_context({})` — Gemini retrieves session state
3. Gemini should describe the proxy assignments and any diagram that has been generated

---

## Step 4: Build the Architecture

1. Say: **"Based on these components, can you design a microservices architecture diagram?"**
2. Gemini generates a Mermaid diagram incorporating the proxy objects
3. The Architecture Diagram tab updates automatically
4. Workflow status shows validation → visualization → animation progress

---

## What to Watch For

- Gemini speaks first — no need for you to initiate
- Gemini automatically selects "imagine" mode when you mention objects on desk
- Proxy objects appear in the Session Notes tab as they're registered
- No manual mode switching needed — Gemini picks the right mode from the function call description
- `TOOL CALL` and `TOOL RESULT` messages confirm function calling is working
