"""Common logging code."""
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import logging
from functools import cache

DEFAULT_FORMATTER: logging.Formatter = logging.Formatter(
    "%(name)s: %(levelname)s: %(message)s",
)
DEFAULT_HANDLER: logging.Handler = logging.StreamHandler()


@cache
def get_logger(
    name: str,
    formatter: logging.Formatter = DEFAULT_FORMATTER,
    handlers: list[logging.Handlers] | None = None,
    level: int | str = logging.DEBUG,
) -> logging.Logger:
    """Get a logger.

    This function returns a logger setup in a structured manner, with the provided
    `formatter`, `handlers`, and `level`.

    The logger is cached between calls to avoid reconfiguring the logger if the
    function is called more than once with the same `name`.

    NOTE: the `handlers` will be modified. If you need to use different handlers
    across different loggers configured with the same `name`, pass in copies of the
    handlers instead of the original handlers themselves.

    Args:
        name: logger name.
        formatter: a `logging.Formatter` object to set for the logger and its
                   respective handlers.
        handlers: a list of `logging.Handler`s to set for the logger.
        level: the level to output in the logger.

    Returns:
        A fully configured `logging.Logger` object.

    """
    handlers = handlers or [DEFAULT_HANDLER]

    logger = logging.getLogger(name)
    logger.setLevel(level)

    for handler in handlers:
        handler.setFormatter(formatter)
        handler.setLevel(level)
        logger.addHandler(handler)

    return logger
