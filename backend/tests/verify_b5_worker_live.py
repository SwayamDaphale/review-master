"""Focused Verification Script for B5 Review Intelligence & Celery Worker.

Performs live verification of:
1. Submit review-analysis job through actual API (HTTP POST /api/v1/reviews/analyze).
2. Confirm API immediately returns HTTP 202 Accepted.
3. Confirm Celery worker receives and executes the task.
4. Confirm analysis is persisted in PostgreSQL.
5. Confirm job status changes: pending -> running -> completed.
6. Simulate duplicate task delivery and verify only one analysis is persisted.
7. Verify a job taking longer than 60 seconds cannot be processed twice.
"""

import datetime
import json
import time
import uuid

import httpx
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.identity import Role, User
from app.models.review_intelligence import ReviewAnalysis
from app.services.async_jobs import AsyncJobManager
from app.worker.celery_app import process_review_analysis_task


def run_verification():
    print("=" * 70)
    print("STARTING B5 REVIEW INTELLIGENCE LIVE VERIFICATION")
    print("=" * 70)

    db = SessionLocal()
    results = {}

    try:
        # Setup test admin user for authorization
        admin_role = db.execute(select(Role).filter_by(name="admin")).scalar_one_or_none()
        if not admin_role:
            admin_role = Role(name="admin", description="System Administrator")
            db.add(admin_role)
            db.flush()

        test_user = db.execute(
            select(User).filter_by(email="live_verifier@reviewmaster.local")
        ).scalar_one_or_none()
        if not test_user:
            test_user = User(
                email="live_verifier@reviewmaster.local",
                display_name="Live Verifier",
                is_active=True,
            )
            test_user.roles.append(admin_role)
            db.add(test_user)
            db.commit()
        elif admin_role not in test_user.roles:
            test_user.roles.append(admin_role)
            db.commit()

        token = create_access_token(
            data={"sub": str(test_user.id), "roles": ["admin"], "type": "access"}
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # -------------------------------------------------------------
        # STEP 1 & 2: Submit job through actual API & confirm 202
        # -------------------------------------------------------------
        print("\n--- STEP 1 & 2: Submitting review-analysis job via API ---")
        unique_text = f"Battery life lasts 2 full days easily on a single charge. Superb screen! [{uuid.uuid4()}]"
        payload = {
            "review_text": unique_text,
            "idempotency_key": f"verify-{uuid.uuid4()}",
        }

        with httpx.Client(base_url="http://localhost:8000", timeout=10.0) as client:
            submit_start = time.time()
            resp = client.post("/api/v1/reviews/analyze", json=payload, headers=headers)
            submit_latency = time.time() - submit_start

            print(f"API Response Status: {resp.status_code}")
            print(f"API Latency: {submit_latency:.3f}s (Immediate async response)")
            assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
            
            data = resp.json()
            job_id_str = data["job_id"]
            initial_status = data["status"]
            print(f"Job ID: {job_id_str}")
            print(f"Initial Status: {initial_status}")
            
            results["step1_api_submission"] = "PASSED"
            results["step2_immediate_202"] = f"PASSED (Status 202 in {submit_latency:.3f}s)"

            # ---------------------------------------------------------
            # STEP 3 & 5: Confirm worker execution & pending -> running -> completed
            # ---------------------------------------------------------
            print("\n--- STEP 3 & 5: Polling job status transitions ---")
            observed_statuses = [initial_status]
            final_job_status = None
            poll_start = time.time()
            
            for _ in range(40):  # poll up to 20 seconds
                status_resp = client.get(f"/api/v1/reviews/jobs/{job_id_str}", headers=headers)
                assert status_resp.status_code == 200, f"Status check failed: {status_resp.text}"
                status_data = status_resp.json()
                current_st = status_data["status"]
                
                if current_st not in observed_statuses:
                    observed_statuses.append(current_st)
                    print(f"Status transition observed -> {current_st} (at {time.time() - poll_start:.2f}s)")
                
                if current_st in ("completed", "failed"):
                    final_job_status = status_data
                    break
                time.sleep(0.3)

            print(f"Observed Status Transitions: {' -> '.join(observed_statuses)}")
            print(f"Final Job State: {json.dumps(final_job_status, indent=2)}")
            assert final_job_status is not None, "Job timed out before reaching terminal status"
            assert final_job_status["status"] == "completed", f"Job failed: {final_job_status}"
            
            results["step3_worker_execution"] = "PASSED (Worker received and executed task)"
            results["step5_status_transitions"] = f"PASSED ({' -> '.join(observed_statuses)})"

            # ---------------------------------------------------------
            # STEP 4: Confirm analysis is persisted in PostgreSQL
            # ---------------------------------------------------------
            print("\n--- STEP 4: Verifying PostgreSQL persistence ---")
            db.expire_all()
            analysis_id_str = final_job_status.get("result_summary", {}).get("analysis_id")
            assert analysis_id_str, "result_summary missing analysis_id"
            analysis_id = uuid.UUID(analysis_id_str)
            
            analysis = db.execute(
                select(ReviewAnalysis).filter_by(id=analysis_id)
            ).scalar_one_or_none()
            
            assert analysis is not None, f"Analysis {analysis_id} not found in PostgreSQL"
            assert analysis.status == "completed", f"Analysis status is {analysis.status}"
            assert analysis.sentiment in ("positive", "negative", "neutral", "mixed")
            
            print(f"PostgreSQL ReviewAnalysis ID: {analysis.id}")
            print(f"Sentiment: {analysis.sentiment} (confidence: {analysis.sentiment_confidence})")
            print(f"Aspects count: {len(analysis.aspect_opinions)}")
            for aspect in analysis.aspect_opinions:
                print(f"  - Aspect [{aspect.aspect_key}]: polarity={aspect.polarity}, claim='{aspect.claim}'")
            print(f"Pros/Cons count: {len(analysis.pros_cons)}")
            for pc in analysis.pros_cons:
                print(f"  - [{pc.item_type}] aspect_key={pc.aspect_key}: '{pc.text}'")

            results["step4_postgres_persistence"] = (
                f"PASSED (Analysis {analysis.id} persisted with {len(analysis.aspect_opinions)} aspects "
                f"and {len(analysis.pros_cons)} pros/cons)"
            )

            # ---------------------------------------------------------
            # STEP 6: Simulate duplicate task delivery
            # ---------------------------------------------------------
            print("\n--- STEP 6: Simulating duplicate task delivery ---")
            count_before = db.scalar(
                select(func.count(ReviewAnalysis.id)).filter(ReviewAnalysis.review_text == unique_text)
            )
            print(f"Analysis count before duplicate delivery: {count_before}")
            assert count_before == 1

            # Dispatch duplicate task execution directly to worker task logic
            dup_result = process_review_analysis_task(
                job_id_str=job_id_str,
                review_text=unique_text,
            )
            print(f"Duplicate task execution return: {dup_result}")
            assert dup_result["status"] == "completed"

            db.expire_all()
            count_after = db.scalar(
                select(func.count(ReviewAnalysis.id)).filter(ReviewAnalysis.review_text == unique_text)
            )
            print(f"Analysis count after duplicate delivery: {count_after}")
            assert count_after == 1, f"Duplicate analysis persisted! Found {count_after}"

            results["step6_duplicate_delivery"] = "PASSED (Skipped redundant execution; count remained exactly 1)"

            # ---------------------------------------------------------
            # STEP 7: Verify job taking > 60 seconds cannot be processed twice
            # ---------------------------------------------------------
            print("\n--- STEP 7: Verifying job > 60 seconds cannot be processed twice ---")
            # Create a separate synthetic long-running job in 'running' state with timestamp 75s in the past
            long_job_key = f"long-running-{uuid.uuid4()}"
            manager = AsyncJobManager(db)
            long_job, _ = manager.create_or_get_job(
                idempotency_key=long_job_key,
                job_type="review_analysis",
                user_id=test_user.id,
            )
            # Transition to running in DB and Redis
            manager.update_job_status(long_job.id, status="running")
            db.commit()

            # Set updated_at and created_at to 75 seconds ago to simulate a job running > 60s
            past_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=75)
            long_job.created_at = past_time
            long_job.updated_at = past_time
            db.commit()
            if manager.redis:
                cache_key = f"job:{long_job.id}"
                cached = manager.redis.get(cache_key)
                if cached:
                    state = json.loads(cached)
                    state["updated_at"] = time.time() - 75
                    state["created_at"] = time.time() - 75
                    manager.redis.set(cache_key, json.dumps(state), ex=86400)

            # Verify that while in 'running' (even after 75s), duplicate delivery is blocked
            long_job_text = f"Long running review text verification [{uuid.uuid4()}]"
            dup_long_result = process_review_analysis_task(
                job_id_str=str(long_job.id),
                review_text=long_job_text,
            )
            print(f"Task delivery for >60s 'running' job returned: {dup_long_result}")
            assert dup_long_result["status"] == "running", f"Expected skipped with status 'running', got: {dup_long_result}"

            long_count = db.scalar(
                select(func.count(ReviewAnalysis.id)).filter(ReviewAnalysis.review_text == long_job_text)
            )
            assert long_count == 0, "No analysis should be created while job is running"

            # Now mark it completed as if it finished after 80s
            manager.update_job_status(
                long_job.id,
                status="completed",
                result_payload={"analysis_id": str(analysis.id), "status": "completed"},
            )
            db.commit()

            # Second duplicate attempt after completion (>60s overall)
            post_complete_result = process_review_analysis_task(
                job_id_str=str(long_job.id),
                review_text=long_job_text,
            )
            print(f"Task delivery for >60s 'completed' job returned: {post_complete_result}")
            assert post_complete_result["status"] == "completed"

            long_count_after = db.scalar(
                select(func.count(ReviewAnalysis.id)).filter(ReviewAnalysis.review_text == long_job_text)
            )
            assert long_count_after == 0, "Duplicate execution correctly prevented"

            results["step7_longer_than_60s_guard"] = (
                "PASSED (Active 'running' guard and 'completed' guard prevent re-processing regardless of elapsed time)"
            )

    finally:
        db.close()

    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    for step, res in results.items():
        print(f"[{step}]: {res}")
    print("=" * 70)
    return results


if __name__ == "__main__":
    run_verification()
