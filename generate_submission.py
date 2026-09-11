"""
Submission Generator for Gen AI Project 2: Intelligent RAG
Reads test.csv, sends each question to the live FastAPI /query endpoint,
and generates submission.csv with all 20 answers.

Usage:
    # Make sure FastAPI backend is running first:
    #   uvicorn app.main:app --reload --port 8000
    
    # Then run:
    python generate_submission.py
    
    # Output: submission.csv (in project root)
"""

import csv
import os
import sys
import time
import requests

# ── Configuration ─────────────────────────────────────────────────────────────
API_URL = (os.getenv("BACKEND_URL") or "http://localhost:8080") + "/query"
TEST_CSV = os.path.join("project-2-intelligent-rag", "test.csv")
OUTPUT_CSV = "submission.csv"
REQUEST_TIMEOUT = 120   # seconds — guardrails + LangGraph + Groq can take >60s
DELAY_BETWEEN = 5       # seconds — stay within Groq rate limits


def main():
    # ── Read test questions ───────────────────────────────────────────────────
    if not os.path.exists(TEST_CSV):
        print(f"❌ Cannot find {TEST_CSV}")
        sys.exit(1)

    questions = []
    with open(TEST_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row["question_id"].strip()
            question = row["question"].strip()
            questions.append((qid, question))

    print(f"📋 Loaded {len(questions)} questions from {TEST_CSV}")
    print(f"🌐 Backend URL: {API_URL}")
    print(f"⏱️  Delay between calls: {DELAY_BETWEEN}s")
    print("=" * 60)

    # ── Query the RAG pipeline for each question ──────────────────────────────
    results = []
    for i, (qid, question) in enumerate(questions):
        print(f"\n[{i+1}/{len(questions)}] {qid}: {question[:70]}...")

        try:
            resp = requests.post(
                API_URL,
                json={"q": question, "thread_id": f"submission_{qid}"},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            answer = data.get("answer", "").strip()
            status = data.get("status", "")
            thought = data.get("thought_process", [])

            # Show status
            if any("guardrails fired" in str(s).lower() for s in thought):
                print(f"  🛡️  Guardrails fired → refusal response")
            else:
                print(f"  ✅ Answer: {answer[:80]}...")

            results.append((qid, answer))

        except requests.exceptions.ConnectionError:
            print(f"  ❌ Cannot reach backend at {API_URL}")
            print(f"     Make sure FastAPI is running: uvicorn app.main:app --reload --port 8000")
            sys.exit(1)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append((qid, "Error generating response."))

        # Rate limit delay (skip after last question)
        if i < len(questions) - 1:
            time.sleep(DELAY_BETWEEN)

    # ── Write submission.csv ──────────────────────────────────────────────────
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question_id", "answer"])
        for qid, answer in results:
            # Clean answer: remove newlines, trim whitespace
            clean_answer = " ".join(answer.split())
            writer.writerow([qid, clean_answer])

    print("\n" + "=" * 60)
    print(f"✅ submission.csv generated with {len(results)} answers!")
    print(f"📁 Output: {os.path.abspath(OUTPUT_CSV)}")
    print(f"\n💡 Upload this file to the competition submission page.")


if __name__ == "__main__":
    main()
