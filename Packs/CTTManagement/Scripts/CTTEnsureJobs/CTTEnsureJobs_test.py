from CTTEnsureJobs import job_body, job_changes, obsolete_jobs, plan_jobs

WANTED = [
    {"name": "A", "playbookId": "A", "humanCron": {"timePeriodType": "hours", "timePeriod": 6}, "timezone": "Asia/Singapore"},
    {"name": "B", "playbookId": "B", "humanCron": {"timePeriodType": "hours", "timePeriod": 6}, "timezone": "Asia/Singapore"},
    {"name": "C", "playbookId": "C", "humanCron": {"timePeriodType": "hours", "timePeriod": 6}, "timezone": "Asia/Singapore"},
]


RUNNABLE = {"parent": "A", "owner": "admin@example.com"}


def test_job_changes():
    current = dict(WANTED[0], id="A", humanCron={"timePeriodType": "hours", "timePeriod": 12}, **RUNNABLE)
    assert job_changes(WANTED[0], current) == ["humanCron"]


def test_job_changes_unrunnable_job():
    """Jobs made by older versions had no category, parent or owner; the scheduler dropped their runs."""
    wanted = dict(WANTED[0], category="job", endingType="never")
    current = dict(WANTED[0], id="A", category="", parent="", owner="")
    assert job_changes(wanted, current) == ["category", "endingType", "parent", "owner"]


def test_plan_jobs():
    existing = [
        dict(WANTED[0], id="A", version=2, **RUNNABLE),
        dict(WANTED[1], id="B", version=1, playbookId="old", parent="B", owner="admin@example.com"),
    ]
    actions = [(a, j["name"], changed) for a, j, _, changed in plan_jobs(WANTED, existing)]
    assert actions == [("ok", "A", []), ("update", "B", ["playbookId"]), ("create", "C", [])]


def test_obsolete_jobs():
    existing = [{"name": "A", "id": "A"}, {"name": "CTT - Weekly Stats", "id": "W"}, {"name": "Someone else", "id": "S"}]
    wanted = [{"name": "A"}]
    assert [j["id"] for j in obsolete_jobs(wanted, existing)] == ["W"]


def test_job_body():
    job = dict(WANTED[0], id="A", parent="A", startDate="2026-11-06T00:00:00Z")
    new = job_body(job, None, "me@example.com")
    assert (new["id"], new["parent"], new["owner"]) == ("A", "A", "me@example.com")
    # A job made in the UI keeps its UUID, start date and owner; parent follows the UUID.
    ui = {"id": "7dbe4e66", "version": 3, "startDate": "2026-11-03T14:00:27Z", "owner": "admin@example.com"}
    upd = job_body(job, ui, "me@example.com")
    assert (upd["id"], upd["parent"], upd["owner"], upd["startDate"], upd["version"]) == (
        "7dbe4e66",
        "7dbe4e66",
        "admin@example.com",
        "2026-11-03T14:00:27Z",
        3,
    )
