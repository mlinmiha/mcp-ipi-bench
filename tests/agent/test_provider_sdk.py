"""Live check that the openai SDK used for OpenRouter is installed."""

import pytest


@pytest.mark.live
def test_openai_sdk_is_importable():
    import openai

    assert openai.OpenAI
