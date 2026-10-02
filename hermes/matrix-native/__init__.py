"""Declare native Matrix dependencies without replacing the bundled adapter."""


def register(ctx):
    """Dependencies are provisioned by PM; no runtime hooks are needed."""
    return None
