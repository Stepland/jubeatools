from typing import Any, Callable, Union

import click


def add_to_dict(
    key: str,
) -> Callable[[click.Context, Union[click.Option, click.Parameter], Any], None]:
    def add_to_key(
        ctx: click.Context, param: Union[click.Option, click.Parameter], value: Any
    ) -> None:
        ctx.params.setdefault(key, {})[param.name] = value

    return add_to_key


def loader_option(*args: Any, **kwargs: Any) -> Callable:
    return click.option(
        *args, callback=add_to_dict("loader_options"), expose_value=False, **kwargs
    )


def dumper_option(*args: Any, **kwargs: Any) -> Callable:
    return click.option(
        *args, callback=add_to_dict("dumper_options"), expose_value=False, **kwargs
    )
