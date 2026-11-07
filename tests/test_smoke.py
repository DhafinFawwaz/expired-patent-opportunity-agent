def test_package_imports() -> None:
    import patentic

    assert patentic.__version__ == "0.1.0"


def test_freellm_importable() -> None:
    from freellm import get_chat_model

    assert callable(get_chat_model)
