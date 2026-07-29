from __future__ import annotations

import schedule

from services.scheduler import register_interval_job


def test_register_interval_job_creates_correct_interval():
    schedule.clear()
    calls = []
    register_interval_job(15, lambda: calls.append(1))
    jobs = schedule.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].interval == 15
    assert jobs[0].unit == "minutes"
    schedule.clear()
