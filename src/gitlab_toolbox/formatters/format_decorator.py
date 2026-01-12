"""Format decorator for CLI commands."""

from functools import wraps
from typing import Callable, Dict, List, Optional

import click

from .display import is_script_context
from .generic_handlers import create_format_handlers


def format_decorator(
    formats: List[str],
    interactive_default: str,
    script_default: str,
    format_handlers: Optional[Dict[str, Callable]] = None,
    entity_type: Optional[str] = None,
) -> Callable:
    """Decorator that adds format switching logic to CLI commands.

    Args:
        formats: List of available format strings for click.Choice
        interactive_default: Default format for interactive mode
        script_default: Default format for script mode (when stdout is not a TTY)
        format_handlers: Dict mapping format names to handler functions.
                          Each handler should accept (data, **kwargs) where kwargs
                          can contain additional formatting options like show_members.
                          If None, will use generic handlers based on entity_type.
        entity_type: Entity type for generic handlers (e.g., 'groups', 'projects').
                      Required if format_handlers is None.

    Returns:
        Decorated function that receives a format_handler parameter
    """

    def decorator(func: Callable) -> Callable:
        # Add the format option to the function
        func = click.option(
            "-o",
            "--output",
            type=click.Choice(formats, case_sensitive=False),
            default=None,
            help=f"Output format ({', '.join(formats)}). Defaults to '{interactive_default}' for interactive, '{script_default}' for scripts.",
        )(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract format from kwargs
            format_choice = kwargs.pop("output", None)

            # Auto-detect format for script context
            if format_choice is None:
                format_choice = script_default if is_script_context() else interactive_default

            # Determine format handlers
            if format_handlers is None:
                if entity_type is None:
                    raise ValueError("Either format_handlers or entity_type must be provided")
                format_handlers_resolved = create_format_handlers(entity_type, formats)
            else:
                format_handlers_resolved = format_handlers

            # Get the handler for this format
            format_handler = format_handlers_resolved.get(format_choice)
            if format_handler is None:
                raise ValueError(f"Unknown format: {format_choice}")

            # Create a partial handler that captures format-specific kwargs
            def format_handler_with_kwargs(data, **format_kwargs):
                return format_handler(data, **format_kwargs)

            # Add format_handler to kwargs
            kwargs["format_handler"] = format_handler_with_kwargs

            # Call the original function
            return func(*args, **kwargs)

        return wrapper

    return decorator
