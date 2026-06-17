import io

from rich.console import Console

from gitlab_toolbox.formatters import display
from gitlab_toolbox.formatters.display import DisplayFormatter
from gitlab_toolbox.models.group import Group


def test_group_table_does_not_prefix_subgroups_with_tree_glyphs(monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr(
        display,
        "console_stdout",
        Console(file=output, force_terminal=False, width=120),
    )
    group = Group(
        id=1,
        name="platform",
        full_path="platform",
        parent_id=None,
        members=[],
        subgroups=[
            Group(
                id=2,
                name="toolbox",
                full_path="platform/toolbox",
                parent_id=1,
                members=[],
                subgroups=[],
            )
        ],
    )

    DisplayFormatter.display_groups_as_table([group], show_members=False)

    rendered = output.getvalue()
    assert "platform/toolbox" in rendered
    assert "└─" not in rendered
