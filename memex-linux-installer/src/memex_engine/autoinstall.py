"""Removed Subiquity scaffold. Kubuntu installation uses the Curtin backend."""


def build_autoinstall(*args, **kwargs):
    raise RuntimeError("Subiquity autoinstall is not the Kubuntu backend. Use memex_engine.backend.build_config.")


def write_autoinstall(*args, **kwargs):
    return build_autoinstall(*args, **kwargs)
