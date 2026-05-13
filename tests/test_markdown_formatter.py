from gitlab_toolbox.formatters.markdown_formatter import MarkdownFormatter
from gitlab_toolbox.models.group import Group, GroupMember


def test_group_members_markdown_repeats_full_group_for_every_member():
    group = Group(
        id=1,
        name="toolbox",
        full_path="platform/toolbox",
        parent_id=None,
        members=[
            GroupMember(
                id=10,
                username="ada",
                name="Ada Lovelace",
                access_level=50,
                access_level_description="Owner",
                state="active",
                membership_state="active",
            ),
            GroupMember(
                id=11,
                username="grace",
                name="Grace Hopper",
                access_level=30,
                access_level_description="Developer",
                state="active",
                membership_state="active",
            ),
        ],
        subgroups=[],
    )

    output = MarkdownFormatter.format_groups([group], show_members=True)

    assert "| platform/toolbox | ada | Ada Lovelace | Owner | active | active |" in output
    assert "| platform/toolbox | grace | Grace Hopper | Developer | active | active |" in output
