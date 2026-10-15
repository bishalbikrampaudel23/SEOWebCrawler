"""Optional Flask dashboard with bounded background scan jobs."""

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from typing import Any

from flask import Flask, jsonify, render_template, request

from .analyzer import analyze_crawl
from .config import CrawlerConfig
from .crawler import Crawler
from .reporting import to_csv
from .security import UnsafeTargetError, validate_target_url

LOGGER = logging.getLogger(__name__)


def create_app(
    config: CrawlerConfig | None = None,
    *,
    executor: Executor | None = None,
) -> Flask:
    """Create the dashboard app; pass an executor for controlled deployments/tests."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
    crawler_config = config or CrawlerConfig()
    job_executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="seo-scan")
    jobs: dict[str, dict[str, Any]] = {}
    jobs_lock = threading.Lock()
    active_slots = threading.BoundedSemaphore(2)

    def execute_scan(job_id: str, target: str) -> None:
        """Run one scan and store its result without exposing exception details."""
        try:
            crawl_result = Crawler(crawler_config).crawl(target)
            report = analyze_crawl(crawl_result)
            with jobs_lock:
                jobs[job_id].update(status="complete", report=report.to_dict())
        except Exception:
            LOGGER.exception("Scan job %s failed", job_id)
            with jobs_lock:
                jobs[job_id].update(status="failed", error="Scan failed; see server logs")
        finally:
            active_slots.release()

    @app.get("/")
    def dashboard() -> str:
        """Render the audit dashboard."""
        return render_template("dashboard.html")

    @app.get("/healthz")
    def health_check():
        """Return a lightweight process health response."""
        return jsonify(status="ok")

    @app.post("/api/scans")
    def start_scan():
        """Validate a target and enqueue a bounded scan job."""
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("url"), str):
            return jsonify(error="Provide a URL in JSON field 'url'."), 400
        try:
            target = validate_target_url(payload["url"])
        except UnsafeTargetError as exc:
            return jsonify(error=str(exc)), 400
        if not active_slots.acquire(blocking=False):
            return jsonify(error="The scan queue is full; try again shortly."), 429
        job_id = uuid.uuid4().hex
        with jobs_lock:
            jobs[job_id] = {"id": job_id, "status": "running"}
            while len(jobs) > 100:
                completed = next(
                    (
                        key
                        for key, value in jobs.items()
                        if value["status"] in {"complete", "failed"}
                    ),
                    None,
                )
                if completed is None:
                    break
                del jobs[completed]
        try:
            future: Future[Any] = job_executor.submit(execute_scan, job_id, target)
            with jobs_lock:
                jobs[job_id]["future"] = future
        except Exception:
            active_slots.release()
            with jobs_lock:
                jobs.pop(job_id, None)
            LOGGER.exception("Could not submit scan job")
            return jsonify(error="Could not start scan."), 503
        return jsonify(id=job_id, status="running"), 202

    @app.get("/api/scans/<job_id>")
    def get_scan(job_id: str):
        """Return the public status and report payload for a scan job."""
        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                return jsonify(error="Scan not found."), 404
            result = {key: value for key, value in job.items() if key != "future"}
        return jsonify(result)

    @app.get("/api/scans/<job_id>/report.csv")
    def download_csv(job_id: str):
        """Download a completed scan as a CSV attachment."""
        with jobs_lock:
            job = jobs.get(job_id)
            if job is None or job.get("status") != "complete":
                return jsonify(error="Completed scan not found."), 404
            report_data = job["report"]
        from .models import PageAnalysis, SiteReport

        pages = [PageAnalysis(**page) for page in report_data["pages"]]
        report = SiteReport(
            start_url=report_data["start_url"],
            pages=pages,
            link_statuses=report_data["link_statuses"],
            generated_at=report_data["generated_at"],
        )
        return app.response_class(
            to_csv(report), mimetype="text/csv",
            headers={"Content-Disposition": f'attachment; filename="seo-report-{job_id}.csv"'},
        )

    app.extensions["seo_job_executor"] = job_executor
    app.extensions["seo_jobs"] = jobs
    return app