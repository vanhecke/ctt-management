from CTTEnsureJobs import job_changes, plan_jobs

WANTED = [
    {"name": "A", "playbookId": "A", "humanCron": {"timePeriodType": "hours", "timePeriod": 6}, "timezone": "Asia/Singapore"},
    {"name": "B", "playbookId": "B", "humanCron": {"timePeriodType": "hours", "timePeriod": 6}, "timezone": "Asia/Singapore"},
    {"name": "C", "playbookId": "C", "humanCron": {"timePeriodType": "hours", "timePeriod": 6}, "timezone": "Asia/Singapore"},
]


def test_job_changes():
    current = dict(WANTED[0], humanCron={"timePeriodType": "hours", "timePeriod": 12})
    assert job_changes(WANTED[0], current) == ["humanCron"]


def test_plan_jobs():
    existing = [dict(WANTED[0], id="A", version=2), dict(WANTED[1], id="B", version=1, playbookId="old")]
    actions = [(a, j["name"], changed) for a, j, _, changed in plan_jobs(WANTED, existing)]
    assert actions == [("ok", "A", []), ("update", "B", ["playbookId"]), ("create", "C", [])]
