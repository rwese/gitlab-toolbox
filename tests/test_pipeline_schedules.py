"""Tests for the `pipeline-schedules` command group."""

import io
import json

from click.testing import CliRunner

from gitlab_toolbox.cli import cli
from gitlab_toolbox.commands import pipeline_schedules as ps_module
from gitlab_toolbox.models.pipeline_schedule import (
    PipelineSchedule,
    PipelineScheduleInput,
    PipelineScheduleVariable,
)


def _make_schedule(**overrides):
    """Return a minimal PipelineSchedule for tests."""
    defaults = dict(
        id=1,
        description="UIUX",
        ref="refs/heads/main",
        cron="25 13 * * *",
        cron_timezone="Etc/UTC",
        next_run_at=None,
        active=True,
        created_at=None,
        updated_at=None,
        owner=None,
        last_pipeline=None,
        variables=[],
        inputs=[],
    )
    defaults.update(overrides)
    return PipelineSchedule(**defaults)


def _invoke(runner, args, stderr_sink):
    """Invoke the CLI with the module-level console's file redirected.

    The export command's trailing status message goes through Rich's
    ``Console.print()`` which uses the ``file`` captured at import time,
    so CliRunner's automatic ``sys.stderr`` swap does not see it. Pointing
    the console at our sink keeps the message inspectable.
    """
    original_file = ps_module.console.file
    ps_module.console.file = stderr_sink
    try:
        return runner.invoke(cli, args)
    finally:
        ps_module.console.file = original_file


def test_export_to_stdout_does_not_crash(monkeypatch):
    """Regression: ``pipeline-schedules export`` must not crash on the trailing
    status message. Previously it raised
    ``TypeError: Console.print() got an unexpected keyword argument 'file'``.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"

    schedules = [
        _make_schedule(
            id=1,
            description="UIUX",
            variables=[
                PipelineScheduleVariable(
                    key="MOCKOON_IMAGE_URL",
                    value="code.anexia.com:4567/ps/projects/automated-testing/mockoon:latest",
                    variable_type="env_var",
                    raw=False,
                )
            ],
        ),
        _make_schedule(
            id=2,
            description="single-test-suite-api",
            cron="22 18 * * *",
            active=False,
        ),
    ]

    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: schedules)

    stderr_sink = io.StringIO()
    result = _invoke(CliRunner(), ["pipeline-schedules", "export"], stderr_sink)

    assert result.exit_code == 0, result.output

    # JSON payload on stdout
    payload = json.loads(result.stdout)
    assert [s["description"] for s in payload] == [
        "UIUX",
        "single-test-suite-api",
    ]

    # Status message on stderr (the line that previously crashed)
    assert "Exported 2 schedule(s)" in stderr_sink.getvalue()


def test_export_with_empty_result_does_not_crash(monkeypatch):
    """Exporting with zero matching schedules should exit cleanly."""
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [])

    stderr_sink = io.StringIO()
    result = _invoke(CliRunner(), ["pipeline-schedules", "export"], stderr_sink)

    assert result.exit_code == 0
    assert "No pipeline schedules found" in stderr_sink.getvalue()


def test_export_to_file_writes_json(monkeypatch, tmp_path):
    """When ``-o`` is provided, JSON should be written to that file."""
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    monkeypatch.setattr(
        PipelineSchedulesAPI,
        "get_schedules",
        lambda *a, **kw: [_make_schedule()],
    )

    out_file = tmp_path / "schedules.json"
    stderr_sink = io.StringIO()
    result = _invoke(
        CliRunner(),
        ["pipeline-schedules", "export", "-o", str(out_file)],
        stderr_sink,
    )

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data[0]["description"] == "UIUX"
    assert "Exported 1 schedule(s)" in stderr_sink.getvalue()


# ---------------------------------------------------------------------------
# Pipeline inputs (GitLab 17.11+/18.1+)
# ---------------------------------------------------------------------------


def test_parse_schedule_from_rest_extracts_inputs():
    """The REST GET response carries ``inputs`` as a list of {name, value} dicts.
    The parser should expose them on the ``PipelineSchedule.inputs`` field.
    """
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    raw = {
        "id": 140,
        "description": "UIUX",
        "ref": "refs/heads/main",
        "cron": "25 13 * * *",
        "cron_timezone": "Etc/UTC",
        "next_run_at": None,
        "active": True,
        "created_at": "2026-03-10T07:14:24.364Z",
        "updated_at": "2026-06-23T13:33:06.961Z",
        "owner": {},
        "last_pipeline": None,
        "variables": [],
        "inputs": [
            {"name": "engine_repository_branch", "value": "integration-uiux"},
            {"name": "automated_testing_npm_script", "value": "pipeline-core-acc"},
            {"name": "mattermost_channel", "value": "engine-automated-testing-core"},
        ],
    }

    schedule = PipelineSchedulesAPI._parse_schedule(raw)

    assert schedule.inputs == [
        PipelineScheduleInput(name="engine_repository_branch", value="integration-uiux"),
        PipelineScheduleInput(name="automated_testing_npm_script", value="pipeline-core-acc"),
        PipelineScheduleInput(name="mattermost_channel", value="engine-automated-testing-core"),
    ]


def test_parse_schedule_from_rest_handles_missing_inputs():
    """Older GitLab versions omit the ``inputs`` field. The parser must still
    return a PipelineSchedule and default ``inputs`` to an empty list.
    """
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    raw = {
        "id": 1,
        "description": "legacy",
        "ref": "refs/heads/main",
        "cron": "0 0 * * *",
        "cron_timezone": "Etc/UTC",
        "next_run_at": None,
        "active": True,
        "created_at": None,
        "updated_at": None,
        "owner": {},
        "last_pipeline": None,
        "variables": [],
    }

    schedule = PipelineSchedulesAPI._parse_schedule(raw)

    assert schedule.inputs == []


def test_parse_schedule_from_graphql_extracts_inputs():
    """The GraphQL response uses ``inputs { nodes { name value } }``; the
    parser should normalise it to the same shape used for REST responses.
    """
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    raw = {
        "id": "gid://gitlab/Ci::PipelineSchedule/140",
        "description": "UIUX",
        "ref": "refs/heads/main",
        "cron": "25 13 * * *",
        "cronTimezone": "Etc/UTC",
        "nextRunAt": None,
        "active": True,
        "createdAt": "2026-03-10T07:14:24.364Z",
        "updatedAt": "2026-06-23T13:33:06.961Z",
        "owner": {},
        "pipelines": {"nodes": []},
        "variables": {"nodes": []},
        "inputs": {
            "nodes": [
                {"name": "engine_repository_branch", "value": "integration-uiux"},
                {"name": "mattermost_channel", "value": "engine-automated-testing-core"},
            ]
        },
    }

    schedule = PipelineSchedulesAPI._parse_schedule_from_graphql(raw)

    assert [inp.name for inp in schedule.inputs] == [
        "engine_repository_branch",
        "mattermost_channel",
    ]
    assert schedule.inputs[0].value == "integration-uiux"


def test_create_schedule_sends_inputs_as_array(monkeypatch):
    """The GitLab REST API rejects the hash form of ``inputs`` with
    "inputs is invalid"; the array form ``[{name, value}, ...]`` is the only
    one that works on POST. Verify we send exactly that shape.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    captured = {}

    def fake_request(endpoint, params=None, method="GET"):
        captured["endpoint"] = endpoint
        captured["params"] = params
        captured["method"] = method
        return {"id": 167, "description": "x"}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedule", staticmethod(lambda *a, **kw: None))

    PipelineSchedulesAPI.create_schedule(
        "group/project",
        {
            "description": "x",
            "ref": "main",
            "cron": "0 0 * * *",
            "inputs": [
                {"name": "branch", "value": "main"},
                # ``_destroy`` is update-only; it must be dropped on create.
                {"name": "old", "value": "x", "_destroy": True},
            ],
        },
    )

    assert captured["method"] == "POST"
    assert captured["params"]["inputs"] == [{"name": "branch", "value": "main"}]


def test_update_schedule_sends_inputs_as_array_with_destroy(monkeypatch):
    """On update the ``_destroy`` flag (and ``inputs_to_destroy``) must be
    forwarded as ``{"name": ..., "_destroy": true}`` entries so the API can
    identify which inputs to drop.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    captured = {}

    def fake_request(endpoint, params=None, method="GET"):
        captured["endpoint"] = endpoint
        captured["params"] = params
        captured["method"] = method
        return {
            "id": 140,
            "description": "UIUX",
            "ref": "refs/heads/main",
            "cron": "25 13 * * *",
            "cron_timezone": "Etc/UTC",
            "next_run_at": None,
            "active": True,
            "created_at": None,
            "updated_at": None,
            "owner": {},
            "last_pipeline": None,
            "variables": [],
            "inputs": [],
        }

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    PipelineSchedulesAPI.update_schedule(
        "group/project",
        140,
        {
            "description": "UIUX",
            "inputs": [
                {"name": "engine_repository_branch", "value": "integration-uiux"},
                {"name": "stale_input", "_destroy": True},
            ],
            "inputs_to_destroy": ["another_stale"],
        },
    )

    assert captured["method"] == "PUT"
    assert captured["params"]["inputs"] == [
        {"name": "engine_repository_branch", "value": "integration-uiux"},
        {"name": "stale_input", "_destroy": True},
        {"name": "another_stale", "_destroy": True},
    ]


def test_export_includes_inputs_by_default(monkeypatch):
    """``pipeline-schedules export`` must include the ``inputs`` array on
    each schedule by default so the resulting JSON can be re-imported.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    schedule = _make_schedule(
        inputs=[
            PipelineScheduleInput(name="branch", value="main"),
            PipelineScheduleInput(name="channel", value="ops"),
        ],
    )
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [schedule])

    result = _invoke(CliRunner(), ["pipeline-schedules", "export"], io.StringIO())

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload[0]["inputs"] == [
        {"name": "branch", "value": "main"},
        {"name": "channel", "value": "ops"},
    ]


def test_export_omits_inputs_with_no_include_flag(monkeypatch):
    """``--no-include-inputs`` drops the ``inputs`` field entirely so
    operators can mix-and-match variable backups with input-free schedules.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    schedule = _make_schedule(
        inputs=[PipelineScheduleInput(name="branch", value="main")],
    )
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [schedule])

    result = _invoke(
        CliRunner(), ["pipeline-schedules", "export", "--no-include-inputs"], io.StringIO()
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert "inputs" not in payload[0]


def test_export_omits_empty_inputs_by_default(monkeypatch):
    """Schedules without inputs (or with --no-include-inputs) should not
    surface an empty ``inputs: []`` in the export, keeping diffs clean for
    projects that have not adopted the newer feature.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [_make_schedule()])

    result = _invoke(CliRunner(), ["pipeline-schedules", "export"], io.StringIO())

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert "inputs" not in payload[0]


def test_import_passes_inputs_to_create(monkeypatch):
    """Importing a JSON payload without an ``id`` field is treated as a new
    schedule; the inputs (and other fields) should be forwarded to
    ``create_schedule`` so the new schedule gets the same input values.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    monkeypatch.setattr(
        PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: []
    )  # nothing exists

    captured = {}

    def fake_create(project_path, schedule_data):
        captured["schedule_data"] = schedule_data
        return None  # don't actually call the API

    monkeypatch.setattr(PipelineSchedulesAPI, "create_schedule", staticmethod(fake_create))

    payload = json.dumps(
        [
            {
                "description": "TEST",
                "ref": "main",
                "cron": "0 0 * * *",
                "inputs": [{"name": "branch", "value": "main"}],
            }
        ]
    )

    result = CliRunner().invoke(
        cli,
        [
            "pipeline-schedules",
            "import",
            "--project",
            "group/project",
            "--accept-schedule-updates",
        ],
        input=payload,
    )

    assert result.exit_code == 0, result.output
    assert captured["schedule_data"]["inputs"] == [{"name": "branch", "value": "main"}]


def test_import_dry_run_reports_input_count(monkeypatch):
    """The dry-run summary should make it obvious how many inputs (and
    variables) would be created, so operators can sanity-check a backup
    before pushing it.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [])

    payload = json.dumps(
        [
            {
                "description": "TEST",
                "ref": "main",
                "cron": "0 0 * * *",
                "variables": [
                    {"key": "FOO", "value": "bar", "variable_type": "env_var", "raw": False}
                ],
                "inputs": [
                    {"name": "branch", "value": "main"},
                    {"name": "channel", "value": "ops"},
                ],
            }
        ]
    )

    stderr_sink = io.StringIO()
    # Need the export/import module console for the dry-run summary line.
    original_file = ps_module.console.file
    ps_module.console.file = stderr_sink
    try:
        result = CliRunner().invoke(
            cli,
            [
                "pipeline-schedules",
                "import",
                "--project",
                "group/project",
                "--accept-schedule-updates",
                "--dry-run",
            ],
            input=payload,
        )
    finally:
        ps_module.console.file = original_file

    assert result.exit_code == 0, result.output
    output = stderr_sink.getvalue()
    assert "1 variable(s)" in output
    assert "2 input(s)" in output


# ---------------------------------------------------------------------------
# Import create-vs-update logic
# ---------------------------------------------------------------------------


def test_import_updates_existing_when_id_matches(monkeypatch):
    """When a JSON entry's ``id`` matches an existing schedule, the import
    should call ``update_schedule`` (and reconcile variables) rather than
    creating a duplicate. The confirm prompt is bypassed with
    --accept-schedule-updates.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    existing = _make_schedule(id=140, description="UIUX")
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [existing])

    update_calls = []
    create_calls = []

    def fake_update(project_path, schedule_id, schedule_data):
        update_calls.append((schedule_id, schedule_data))
        return existing

    def fake_create(project_path, schedule_data):
        create_calls.append(schedule_data)
        return None

    monkeypatch.setattr(PipelineSchedulesAPI, "update_schedule", staticmethod(fake_update))
    monkeypatch.setattr(PipelineSchedulesAPI, "create_schedule", staticmethod(fake_create))
    monkeypatch.setattr(
        PipelineSchedulesAPI,
        "set_schedule_variables",
        staticmethod(lambda *a, **kw: None),
    )

    payload = json.dumps(
        [
            {
                "id": 140,
                "description": "UIUX",
                "ref": "refs/heads/main",
                "cron": "25 13 * * *",
                "cron_timezone": "Etc/UTC",
                "active": True,
                "inputs": [{"name": "engine_repository_branch", "value": "main"}],
            }
        ]
    )

    result = CliRunner().invoke(
        cli,
        [
            "pipeline-schedules",
            "import",
            "--project",
            "group/project",
            "--accept-schedule-updates",
        ],
        input=payload,
    )

    assert result.exit_code == 0, result.output
    assert len(update_calls) == 1
    assert update_calls[0][0] == 140
    # The id must be stripped from the payload: the API infers the id from
    # the URL, and a stray id field can confuse downstream handlers.
    assert "id" not in update_calls[0][1]
    assert update_calls[0][1]["inputs"] == [{"name": "engine_repository_branch", "value": "main"}]
    assert create_calls == []


def test_import_reconciles_variables_on_update(monkeypatch):
    """Updating an existing schedule must call ``set_schedule_variables`` with
    the JSON's variables list so the legacy ``/variables`` sub-endpoints
    stay in sync (delete / update / create).
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    existing = _make_schedule(id=140, description="UIUX")
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [existing])
    monkeypatch.setattr(
        PipelineSchedulesAPI,
        "update_schedule",
        staticmethod(lambda *a, **kw: existing),
    )

    reconcile_calls = []

    def fake_reconcile(project_path, schedule_id, variables):
        reconcile_calls.append((project_path, schedule_id, variables))

    monkeypatch.setattr(
        PipelineSchedulesAPI,
        "set_schedule_variables",
        staticmethod(fake_reconcile),
    )

    payload = json.dumps(
        [
            {
                "id": 140,
                "description": "UIUX",
                "ref": "refs/heads/main",
                "cron": "25 13 * * *",
                "cron_timezone": "Etc/UTC",
                "active": True,
                "variables": [
                    {"key": "FOO", "value": "bar", "variable_type": "env_var", "raw": False}
                ],
            }
        ]
    )

    result = CliRunner().invoke(
        cli,
        [
            "pipeline-schedules",
            "import",
            "--project",
            "group/project",
            "--accept-schedule-updates",
        ],
        input=payload,
    )

    assert result.exit_code == 0, result.output
    assert reconcile_calls == [
        (
            "group/project",
            140,
            [
                {
                    "key": "FOO",
                    "value": "bar",
                    "variable_type": "env_var",
                    "raw": False,
                }
            ],
        )
    ]


def test_import_creates_when_id_missing(monkeypatch):
    """Entries without an ``id`` are treated as new schedules, even when
    a schedule with the same description already exists (the old-export
    case). The duplicate warning is surfaced but the create still goes
    through with --accept-schedule-updates.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    existing = _make_schedule(id=140, description="UIUX")
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [existing])

    create_calls = []
    update_calls = []

    def fake_create(project_path, schedule_data):
        create_calls.append(schedule_data)
        return _make_schedule(id=999, description=schedule_data.get("description", ""))

    def fake_update(*a, **kw):
        update_calls.append((a, kw))
        return None

    monkeypatch.setattr(PipelineSchedulesAPI, "create_schedule", staticmethod(fake_create))
    monkeypatch.setattr(PipelineSchedulesAPI, "update_schedule", staticmethod(fake_update))

    payload = json.dumps(
        [
            {
                # No ``id`` here — this is an old-style export.
                "description": "UIUX",
                "ref": "main",
                "cron": "0 0 * * *",
            }
        ]
    )

    result = CliRunner().invoke(
        cli,
        [
            "pipeline-schedules",
            "import",
            "--project",
            "group/project",
            "--accept-schedule-updates",
        ],
        input=payload,
    )

    assert result.exit_code == 0, result.output
    assert len(create_calls) == 1
    assert update_calls == []


def test_import_rejects_stale_id(monkeypatch):
    """If a JSON entry has an ``id`` that does not exist in the target
    project, the import must surface the error and not silently create a
    duplicate. The id clearly indicates intent to update, so a missing
    schedule is a hard failure.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [])

    create_calls = []
    update_calls = []

    monkeypatch.setattr(
        PipelineSchedulesAPI,
        "create_schedule",
        staticmethod(lambda *a, **kw: create_calls.append(a) or None),
    )
    monkeypatch.setattr(
        PipelineSchedulesAPI,
        "update_schedule",
        staticmethod(lambda *a, **kw: update_calls.append(a) or None),
    )

    payload = json.dumps([{"id": 9999, "description": "GONE", "ref": "main", "cron": "0 0 * * *"}])

    stderr_sink = io.StringIO()
    original_file = ps_module.console.file
    ps_module.console.file = stderr_sink
    try:
        result = CliRunner().invoke(
            cli,
            [
                "pipeline-schedules",
                "import",
                "--project",
                "group/project",
                "--accept-schedule-updates",
            ],
            input=payload,
        )
    finally:
        ps_module.console.file = original_file

    assert result.exit_code == 0, result.output
    assert create_calls == []
    assert update_calls == []
    output = stderr_sink.getvalue()
    assert "id=9999" in output
    assert "stale" in output.lower()


def test_import_dry_run_shows_mixed_plan(monkeypatch):
    """A dry-run import with both an existing and a new entry must print a
    plan that distinguishes updates from creates, without hitting the API.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    existing = _make_schedule(id=140, description="UIUX")
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [existing])

    api_calls = []

    def explode(*a, **kw):
        api_calls.append((a, kw))
        raise AssertionError("dry-run should not hit the API")

    monkeypatch.setattr(PipelineSchedulesAPI, "create_schedule", staticmethod(explode))
    monkeypatch.setattr(PipelineSchedulesAPI, "update_schedule", staticmethod(explode))

    payload = json.dumps(
        [
            {
                "id": 140,
                "description": "UIUX",
                "ref": "refs/heads/main",
                "cron": "25 13 * * *",
                "cron_timezone": "Etc/UTC",
                "active": True,
            },
            {
                "description": "NEW-ONE",
                "ref": "main",
                "cron": "0 9 * * *",
            },
        ]
    )

    stderr_sink = io.StringIO()
    original_file = ps_module.console.file
    ps_module.console.file = stderr_sink
    try:
        result = CliRunner().invoke(
            cli,
            [
                "pipeline-schedules",
                "import",
                "--project",
                "group/project",
                "--dry-run",
            ],
            input=payload,
        )
    finally:
        ps_module.console.file = original_file

    assert result.exit_code == 0, result.output
    assert api_calls == []
    output = stderr_sink.getvalue()
    assert "Update existing:" in output
    assert "Create new:" in output
    assert "Would update: #140 UIUX" in output
    assert "Would create: NEW-ONE" in output


def test_export_includes_id(monkeypatch):
    """The export format must include the schedule ``id`` so the matching
    import can update existing entries in place. This is the wire that
    makes the export/import round-trip idempotent.
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    schedule = _make_schedule(id=140, description="UIUX")
    monkeypatch.setattr(PipelineSchedulesAPI, "get_schedules", lambda *a, **kw: [schedule])

    result = _invoke(CliRunner(), ["pipeline-schedules", "export"], io.StringIO())

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload[0]["id"] == 140


def test_set_schedule_variables_reconciles(monkeypatch):
    """``set_schedule_variables`` must delete variables that are not in the
    desired set, create new ones, and leave untouched ones alone (so the
    second call is idempotent).
    """
    from gitlab_toolbox.api.client import GitLabClient
    from gitlab_toolbox.api.pipeline_schedules import PipelineSchedulesAPI

    GitLabClient._repo_path = "group/project"
    current = _make_schedule(
        id=140,
        variables=[
            PipelineScheduleVariable(key="KEEP", value="same", variable_type="env_var", raw=False),
            PipelineScheduleVariable(key="DROP", value="old", variable_type="env_var", raw=False),
        ],
    )
    monkeypatch.setattr(
        PipelineSchedulesAPI, "get_schedule", staticmethod(lambda *a, **kw: current)
    )

    deleted = []
    created = []
    updated = []

    monkeypatch.setattr(
        PipelineSchedulesAPI,
        "delete_schedule_variable",
        staticmethod(lambda p, s, k: deleted.append(k) or True),
    )
    monkeypatch.setattr(
        PipelineSchedulesAPI,
        "create_schedule_variable",
        staticmethod(
            lambda p, s, v: created.append(v)
            or PipelineScheduleVariable(
                key=v["key"],
                value=v["value"],
                variable_type=v.get("variable_type", "env_var"),
                raw=v.get("raw", False),
            )
        ),
    )
    monkeypatch.setattr(
        PipelineSchedulesAPI,
        "update_schedule_variable",
        staticmethod(
            lambda p, s, k, v: updated.append((k, v))
            or PipelineScheduleVariable(
                key=k,
                value=v["value"],
                variable_type=v.get("variable_type", "env_var"),
                raw=v.get("raw", False),
            )
        ),
    )

    PipelineSchedulesAPI.set_schedule_variables(
        "group/project",
        140,
        [
            # Unchanged: should not trigger an update.
            {"key": "KEEP", "value": "same", "variable_type": "env_var", "raw": False},
            # Changed value: should trigger an update.
            {"key": "CHANGED", "value": "new", "variable_type": "env_var", "raw": False},
            # Brand new: should be created.
            {"key": "NEW", "value": "v", "variable_type": "env_var", "raw": False},
        ],
    )

    # CHANGED is not on the schedule yet, so it is created (not updated) on
    # the first run. KEEP stays, DROP is removed, NEW is added.
    assert deleted == ["DROP"]
    assert [c["key"] for c in created] == ["CHANGED", "NEW"]
    assert updated == []
