from importlib import resources

import yaml


def read_yaml(name: str) -> object:
    text: str = resources.files("patentic.config").joinpath(name).read_text(encoding="utf-8")
    loaded: object = yaml.safe_load(text)
    return loaded
