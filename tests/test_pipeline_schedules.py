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
    """Importing a JSON payload that contains ``inputs`` should forward them
    to ``create_schedule`` so the new schedule gets the same input values.
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
        ["pipeline-schedules", "import", "--project", "group/project", "--no-skip-existing"],
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
                "--no-skip-existing",
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
