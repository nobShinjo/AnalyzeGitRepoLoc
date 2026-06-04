"""Runtime helpers for the init wizard prompt_toolkit UI.

Description:
    Hosts the prompt_toolkit event loop, selection filters, and key binding
    registration for the full-screen init wizard so the main controller module
    can stay focused on state transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from colorama import just_fix_windows_console


@dataclass(frozen=True)
class _PromptToolkitRuntime:
    """Lazily imported prompt_toolkit runtime objects."""

    application_cls: Any
    condition_cls: Any
    ansi_cls: Any
    key_bindings_cls: Any
    hsplit_cls: Any
    layout_cls: Any
    window_cls: Any
    formatted_text_control_cls: Any
    text_area_cls: Any


def _load_prompt_toolkit() -> _PromptToolkitRuntime:
    """Import prompt_toolkit runtime symbols lazily for --init."""
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.widgets import TextArea
    except ImportError as ex:
        raise RuntimeError(
            "prompt_toolkit is required for --init. "
            "Install dependencies with `uv sync --active`."
        ) from ex
    return _PromptToolkitRuntime(
        application_cls=Application,
        condition_cls=Condition,
        ansi_cls=ANSI,
        key_bindings_cls=KeyBindings,
        hsplit_cls=HSplit,
        layout_cls=Layout,
        window_cls=Window,
        formatted_text_control_cls=FormattedTextControl,
        text_area_cls=TextArea,
    )


def _build_selection_filters(condition: Any, controller: Any) -> dict[str, Any]:
    """Create prompt_toolkit filters for the wizard selection steps."""
    filters = {
        "provider": condition(
            lambda: controller.step == 1 and not controller.needs_self_hosted_url()
        ),
        "interval": condition(lambda: controller.current_field_key() == "interval"),
        "cache_policy": condition(
            lambda: controller.current_field_key() == "cache_policy"
        ),
        "exclude_template_mode": condition(
            lambda: controller.current_field_key() == "exclude_template_mode"
        ),
        "exclude_template_names": condition(
            lambda: controller.current_field_key() == "exclude_template_names"
        ),
        "yes_no": condition(
            lambda: controller.current_field_key() in {"overwrite", "open_plots"}
        ),
        "languages": condition(lambda: controller.current_field_key() == "languages"),
    }
    filters["selection"] = (
        filters["provider"]
        | filters["interval"]
        | filters["cache_policy"]
        | filters["exclude_template_mode"]
        | filters["exclude_template_names"]
        | filters["yes_no"]
        | filters["languages"]
    )
    return filters


def _register_selection_handlers(
    register_refresh_handler: Callable[..., None],
    controller: Any,
    filters: dict[str, Any],
) -> None:
    """Register key handlers for wizard selection lists."""
    for key, action, filter_name in (
        ("up", controller.move_up, "selection"),
        ("down", controller.move_down, "selection"),
        (" ", controller.toggle_current_provider, "provider"),
        (" ", controller.select_current_interval, "interval"),
        (" ", controller.select_current_cache_policy, "cache_policy"),
        (
            " ",
            controller.select_current_exclude_template_mode,
            "exclude_template_mode",
        ),
        (" ", controller.toggle_current_exclude_template, "exclude_template_names"),
        (" ", controller.select_current_yes_no, "yes_no"),
    ):
        register_refresh_handler(key, action, filter_obj=filters[filter_name])
    for key in ("y", "n"):
        register_refresh_handler(
            key,
            lambda key=key: controller.apply_yes_no_shortcut(key),
            filter_obj=filters["yes_no"],
        )


def _build_render_control(
    controller: Any,
    input_field: Any,
    ansi_cls: Any,
) -> Callable[[], object]:
    """Create the formatted text render callback for the wizard view."""

    def render_control() -> object:
        if controller.current_field_key() == "languages":
            controller.update_language_query(input_field.text)
        return ansi_cls(controller.render())

    return render_control


def _build_refresh_input(
    controller: Any,
    input_field: Any,
    get_app: Callable[[], Any | None],
) -> Callable[[], None]:
    """Create the input refresh callback for controller changes."""

    def refresh_input() -> None:
        value = controller.current_value()
        input_field.text = value
        input_field.buffer.cursor_position = len(value)
        app = get_app()
        if app is not None:
            app.invalidate()

    return refresh_input


def _build_register_refresh_handler(
    kb: Any,
    refresh_input: Callable[[], None],
) -> Callable[..., None]:
    """Create a helper that registers simple key handlers."""

    def register_refresh_handler(
        key: str,
        action: Callable[[], None],
        *,
        filter_obj: Any = None,
    ) -> None:
        if filter_obj is None:
            @kb.add(key)
            def _handler(_: object) -> None:
                action()
                refresh_input()

            return

        @kb.add(key, filter=filter_obj)
        def _handler(_: object) -> None:
            action()
            refresh_input()

    return register_refresh_handler


def _register_language_toggle(
    kb: Any,
    controller: Any,
    input_field: Any,
    refresh_input: Callable[[], None],
    language_filter: Any,
) -> None:
    """Register the language picker toggle handler."""

    @kb.add(" ", filter=language_filter)
    def _toggle_language(_: object) -> None:
        controller.update_language_query(input_field.text)
        if controller.language_query:
            controller.toggle_selected_language_suggestion()
        else:
            controller.toggle_current_language()
        refresh_input()


def _register_submit_and_cancel_handlers(
    kb: Any,
    controller: Any,
    input_field: Any,
    filters: dict[str, Any],
    refresh_input: Callable[[], None],
    get_app: Callable[[], Any | None],
) -> None:
    """Register submit and cancel handlers for the wizard."""

    @kb.add("enter")
    def _submit(_: object) -> None:
        if filters["languages"]():
            controller.update_language_query(input_field.text)
        if controller.apply_current_input(input_field.text):
            app = get_app()
            if controller.confirmed and app is not None:
                app.exit()
                return
            refresh_input()

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(_: object) -> None:
        controller.cancel()
        app = get_app()
        if app is not None:
            app.exit()


def _build_application(
    runtime: _PromptToolkitRuntime,
    control: Any,
    input_field: Any,
    kb: Any,
) -> Any:
    """Build the prompt_toolkit application instance."""
    return runtime.application_cls(
        layout=runtime.layout_cls(
            runtime.hsplit_cls(
                [
                    runtime.window_cls(content=control, always_hide_cursor=True),
                    input_field,
                ]
            )
        ),
        key_bindings=kb,
        full_screen=True,
    )


def run_prompt_toolkit_wizard(controller: Any) -> None:
    """Run the prompt_toolkit wizard loop for the provided controller."""
    runtime = _load_prompt_toolkit()

    just_fix_windows_console()
    input_field = runtime.text_area_cls(height=1, prompt="Value: ", multiline=False)
    input_field.text = controller.current_value()

    app: Any | None = None
    kb = runtime.key_bindings_cls()
    get_app = lambda: app
    render_control = _build_render_control(controller, input_field, runtime.ansi_cls)
    refresh_input = _build_refresh_input(controller, input_field, get_app)
    control = runtime.formatted_text_control_cls(render_control)

    filters = _build_selection_filters(runtime.condition_cls, controller)
    register_refresh_handler = _build_register_refresh_handler(kb, refresh_input)

    _register_selection_handlers(register_refresh_handler, controller, filters)
    _register_language_toggle(
        kb,
        controller,
        input_field,
        refresh_input,
        filters["languages"],
    )
    register_refresh_handler("c-b", controller.back)
    _register_submit_and_cancel_handlers(
        kb,
        controller,
        input_field,
        filters,
        refresh_input,
        get_app,
    )
    application = _build_application(runtime, control, input_field, kb)
    app = application
    application.run()
