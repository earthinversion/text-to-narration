"""Real tokenizer regressions; no model weights or speech synthesis required."""

import pytest

kokoro = pytest.importorskip("kokoro_onnx")


@pytest.fixture(scope="module")
def tokenizer():
    return kokoro.Tokenizer()


@pytest.mark.parametrize(
    "text",
    [
        "AI",
        "AI improves reasoning.",
        "The future of AI.",
        "AI-based reasoning.",
        "AI's future.",
        "AI’s future.",
        "What AI agents can learn.",
        "An AI agent suggests a solution.",
        "I use AI, while AIR and OpenAI remain unchanged.",
    ],
)
def test_ai_has_both_letter_names(tokenizer, text):
    # Test the real pinned Kokoro tokenizer, not a mocked pronunciation.
    phonemes = tokenizer.phonemize(text, "en-us")
    assert "ˌeɪˈaɪ" in phonemes


def test_spaced_ai_is_not_a_safe_letter_name_recipe(tokenizer):
    assert tokenizer.phonemize("AI", "en-us") == "ˌeɪˈaɪ"
    assert tokenizer.phonemize("A I", "en-us") == "ɐ ˈaɪ"
