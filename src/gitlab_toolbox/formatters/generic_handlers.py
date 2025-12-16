"""Generic format handlers for all entity types."""

import sys
from typing import Dict, Callable, Any, List

from .display import DisplayFormatter
from .json_formatter import JSONFormatter
from .csv_formatter import CSVFormatter
from .markdown_formatter import MarkdownFormatter


class FormatHandlerRegistry:
    """Registry for creating generic format handlers."""

    # Mapping of format names to (formatter_class, method_pattern, is_display_formatter)
    FORMATTER_MAPPING = {
        "json": (JSONFormatter, "format_{entity_type}", True),  # Returns string, needs print
        "csv": (CSVFormatter, "format_{entity_type}", True),  # Returns string, needs print
        "markdown": (
            MarkdownFormatter,
            "format_{entity_type}",
            True,
        ),  # Returns string, needs print
        "table": (DisplayFormatter, "display_{entity_type}_table", False),  # Direct display
        "tree": (DisplayFormatter, "display_{entity_type}_as_tree", False),  # Direct display
        "details": (DisplayFormatter, "display_{entity_type}_details", False),  # Direct display
    }

    # Default method patterns for each format type
    DEFAULT_PATTERNS = {
        "table": "display_{entity_type}_table",
        "tree": "display_{entity_type}_as_tree",
        "details": "display_{entity_type}_details",
    }

    # Special method name mappings for display methods (since naming is inconsistent)
    SPECIAL_METHOD_NAMES = {
        # Table methods
        ("groups", "table"): "display_groups_as_table",
        ("projects", "table"): "display_projects_table",
        ("merge_requests", "table"): "display_merge_requests_table",
        ("pipelines", "table"): "display_pipelines_table",
        ("pipeline_schedules", "table"): "display_pipeline_schedules_table",
        ("jobs", "table"): "display_pipeline_jobs",
        # Tree methods
        ("groups", "tree"): "display_groups_as_tree",
        # Details methods
        ("project", "details"): "display_project_details",
        ("merge_request", "details"): "display_merge_request_details",
        ("pipeline_schedule", "details"): "display_pipeline_schedule_details",
    }

    # Mapping from singular entity types to plural for JSON/CSV formatters
    SINGULAR_TO_PLURAL = {
        "project": "projects",
        "merge_request": "merge_requests",
        "pipeline_schedule": "pipeline_schedules",
    }

    @classmethod
    def create_format_handlers(cls, entity_type: str, formats: List[str]) -> Dict[str, Callable]:
        """Create format handlers for the given entity type and formats.

        Args:
            entity_type: The entity type (e.g., 'groups', 'projects', 'merge_requests')
            formats: List of format names to create handlers for

        Returns:
            Dict mapping format names to handler functions
        """
        handlers = {}

        for format_name in formats:
            if format_name not in cls.FORMATTER_MAPPING:
                raise ValueError(f"Unknown format: {format_name}")

            formatter_class, method_pattern, returns_string = cls.FORMATTER_MAPPING[format_name]

            # Check for special method name mapping first
            special_key = (entity_type, format_name)
            if special_key in cls.SPECIAL_METHOD_NAMES:
                method_name = cls.SPECIAL_METHOD_NAMES[special_key]
            else:
                # For JSON/CSV formatters, use plural entity type
                if (
                    format_name in ["json", "csv", "markdown"]
                    and entity_type in cls.SINGULAR_TO_PLURAL
                ):
                    entity_type_for_method = cls.SINGULAR_TO_PLURAL[entity_type]
                else:
                    entity_type_for_method = entity_type

                # Use default pattern for this format type if available
                if format_name in cls.DEFAULT_PATTERNS:
                    method_name = cls.DEFAULT_PATTERNS[format_name].format(
                        entity_type=entity_type_for_method
                    )
                else:
                    # Fall back to the generic pattern
                    method_name = method_pattern.format(entity_type=entity_type_for_method)

            # Get the formatter method
            try:
                formatter_method = getattr(formatter_class, method_name)
            except AttributeError:
                raise ValueError(
                    f"Formatter method '{method_name}' not found in {formatter_class.__name__}"
                )
            except AttributeError:
                raise ValueError(
                    f"Formatter method '{method_name}' not found in {formatter_class.__name__}"
                )

            # Create the handler function
            if returns_string:
                # For formatters that return strings, print the result
                # Use default parameter to capture the method in closure
                def string_handler(data, formatter_method=formatter_method, **kwargs):
                    result = formatter_method(data, **kwargs)
                    print(result)

                handlers[format_name] = string_handler
            else:
                # For display formatters, call directly
                handlers[format_name] = formatter_method

        return handlers


def create_format_handlers(entity_type: str, formats: List[str]) -> Dict[str, Callable]:
    """Convenience function to create format handlers.

    Args:
        entity_type: The entity type (e.g., 'groups', 'projects')
        formats: List of format names

    Returns:
        Dict mapping format names to handler functions
    """
    return FormatHandlerRegistry.create_format_handlers(entity_type, formats)
