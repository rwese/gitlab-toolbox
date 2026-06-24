"""Tests for the `pipeline-schedules` command group."""

import io
import json

from click.testing import CliRunner

from gitlab_toolbox.cli import cli
from gitlab_toolbox.commands import pipeline_schedules as ps_module
from gitlab_toolbox.models.pipeline_schedule import (
    PipelineSchedule,
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
