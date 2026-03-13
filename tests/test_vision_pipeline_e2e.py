"""End-to-end automated test for the FUSE vision pipeline.

Sends the HRM architecture test image through the full pipeline:
1. POST /vision/frame — send image, confirm processing
2. GET /state/mermaid — confirm architectural diagram was created
3. GET /validate — confirm validation runs
4. GET /render/realistic — confirm Imagen generates an image
5. GET /render/animate — confirm Veo3 generates a video

All outputs are saved to tests/outputs/ for review.
"""
import httpx
import os
import sys
import time
import json

BASE_URL = os.getenv("FUSE_URL", "https://fuse-service-864533297567.us-central1.run.app")
TEST_IMAGE = os.path.join(os.path.dirname(__file__), "hrm_architecture_test.jpg")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")

os.makedirs(OUTPUT_DIR, exist_ok=True)

results = {}

def log(step, status, detail=""):
    icon = "PASS" if status == "pass" else "FAIL" if status == "fail" else "SKIP"
    print(f"  [{icon}] {step}: {detail}")
    results[step] = {"status": status, "detail": detail}

def run():
    print(f"\n{'='*60}")
    print(f"  FUSE Vision Pipeline E2E Test")
    print(f"  Target: {BASE_URL}")
    print(f"  Image:  {TEST_IMAGE}")
    print(f"{'='*60}\n")

    # Pre-check: health
    print("[1/6] Health Check...")
    try:
        with httpx.Client(timeout=15) as c:
            r = c.get(f"{BASE_URL}/health")
            health = r.json()
            status = health.get("status", "unknown")
            components = health.get("components", {})
            log("health", "pass" if status in ("ok", "degraded") else "fail",
                f"status={status}, vision={'ok' if components.get('gemini_vision', {}).get('status') == 'ok' else 'ERROR'}")
    except Exception as e:
        log("health", "fail", str(e))
        print("\n  ABORTING: Cannot reach server.\n")
        return False

    # Step 1: POST /vision/frame
    print("[2/6] Sending test image to /vision/frame...")
    try:
        with open(TEST_IMAGE, "rb") as f:
            img_bytes = f.read()
        with httpx.Client(timeout=60) as c:
            r = c.post(
                f"{BASE_URL}/vision/frame?mode=whiteboard",
                content=img_bytes,
                headers={"Content-Type": "application/octet-stream"}
            )
            data = r.json()
            if data.get("status") == "success":
                log("vision_frame", "pass", f"mermaid_length={data.get('mermaid_length', 0)}")
            else:
                log("vision_frame", "fail", json.dumps(data))
    except Exception as e:
        log("vision_frame", "fail", str(e))

    # Step 2: GET /state/mermaid
    print("[3/6] Checking /state/mermaid for diagram...")
    try:
        with httpx.Client(timeout=15) as c:
            r = c.get(f"{BASE_URL}/state/mermaid")
            data = r.json()
            mermaid = data.get("mermaid_code")
            if mermaid and len(mermaid) > 10:
                log("mermaid_state", "pass", f"length={len(mermaid)}, starts_with={mermaid[:60]}...")
                with open(os.path.join(OUTPUT_DIR, "mermaid_diagram.txt"), "w") as f:
                    f.write(mermaid)
            else:
                log("mermaid_state", "fail", f"Empty or no mermaid code: {data}")
    except Exception as e:
        log("mermaid_state", "fail", str(e))

    # Step 3: GET /validate
    print("[4/6] Running /validate...")
    try:
        with httpx.Client(timeout=60) as c:
            r = c.get(f"{BASE_URL}/validate")
            data = r.json()
            if data.get("status") == "success":
                report = data.get("validation_report", "")
                is_valid = data.get("is_valid")
                log("validate", "pass", f"is_valid={is_valid}, report_length={len(report)}")
                with open(os.path.join(OUTPUT_DIR, "validation_report.txt"), "w") as f:
                    f.write(f"is_valid: {is_valid}\n\n{report}")
            else:
                log("validate", "fail", json.dumps(data))
    except Exception as e:
        log("validate", "fail", str(e))

    # Step 4: GET /render/realistic
    print("[5/6] Generating Imagen visualization via /render/realistic...")
    try:
        with httpx.Client(timeout=120) as c:
            r = c.get(f"{BASE_URL}/render/realistic")
            if r.headers.get("content-type", "").startswith("image/"):
                out = os.path.join(OUTPUT_DIR, "realistic_visualization.png")
                with open(out, "wb") as f:
                    f.write(r.content)
                log("imagen", "pass", f"saved {len(r.content)} bytes to {out}")
            else:
                data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text[:200]}
                log("imagen", "fail", json.dumps(data))
    except Exception as e:
        log("imagen", "fail", str(e))

    # Step 5: GET /render/animate
    print("[6/6] Generating Veo3 animation via /render/animate...")
    try:
        with httpx.Client(timeout=300) as c:
            r = c.get(f"{BASE_URL}/render/animate")
            if r.headers.get("content-type", "").startswith("video/"):
                out = os.path.join(OUTPUT_DIR, "animation.mp4")
                with open(out, "wb") as f:
                    f.write(r.content)
                log("veo3", "pass", f"saved {len(r.content)} bytes to {out}")
            else:
                data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text[:200]}
                log("veo3", "fail", json.dumps(data))
    except Exception as e:
        log("veo3", "fail", str(e))

    # Summary
    print(f"\n{'='*60}")
    print("  RESULTS SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for v in results.values() if v["status"] == "pass")
    total = len(results)
    for step, r in results.items():
        icon = "+" if r["status"] == "pass" else "-"
        print(f"  [{icon}] {step}: {r['detail'][:80]}")
    print(f"\n  {passed}/{total} steps passed.\n")

    # Save full results
    with open(os.path.join(OUTPUT_DIR, "test_results.json"), "w") as f:
        json.dump(results, f, indent=2)

    return passed == total

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
