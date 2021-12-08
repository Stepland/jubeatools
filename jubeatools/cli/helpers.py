from typing import Any, Callable, Union

import click


def loader_option(*args: Any, **kwargs: Any) -> Callable:
    return click.option(
        *args, callback=add_to_dict("loader_options"), expose_value=False, **kwargs
    )


def dumper_option(*args: Any, **kwargs: Any) -> Callable:
    return click.option(
        *args, callback=add_to_dict("dumper_options"), expose_value=False, **kwargs
    )


def add_to_dict(
    key: str,
) -> Callable[[click.Context, Union[click.Option, click.Parameter], Any], None]:
    def add_to_key(
        ctx: click.Context, param: Union[click.Option, click.Parameter], value: Any
    ) -> None:
        # Avoid shadowing load/dump functions kwargs default values with the
        # default values chosen by click
        assert param.name is not None
        if not parameter_is_a_click_default(ctx, param.name):
            ctx.params.setdefault(key, {})[param.name] = value

    return add_to_key


def parameter_is_a_click_default(
    ctx: click.Context,
    name: str,
) -> bool:
    return ctx.get_parameter_source(name) in (
        click.core.ParameterSource.DEFAULT,
        click.core.ParameterSource.DEFAULT_MAP,
    )
