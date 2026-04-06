"""Tests for SentenceBuffer sentence detection logic."""

import pytest
from app.voice.tts import SentenceBuffer


def test_no_sentence_below_min_chars():
    buf = SentenceBuffer(min_chars=30)
    result = buf.feed("Hi.")
    assert result == []


def test_sentence_returned_when_min_chars_met():
    buf = SentenceBuffer(min_chars=30)
    result = buf.feed("Frans has over five years of experience.")
    assert result == ["Frans has over five years of experience."]


def test_remainder_stays_in_buffer():
    buf = SentenceBuffer(min_chars=30)
    buf.feed("Frans has over five years of experience.")
    result = buf.feed(" He led")
    assert result == []


def test_multiple_sentences_in_one_feed():
    buf = SentenceBuffer(min_chars=10)
    result = buf.feed("Hello world. Goodbye world.")
    assert result == ["Hello world.", "Goodbye world."]


def test_flush_returns_remaining():
    buf = SentenceBuffer(min_chars=30)
    buf.feed("Frans is a data")
    remaining = buf.flush()
    assert remaining == "Frans is a data"


def test_flush_clears_buffer():
    buf = SentenceBuffer(min_chars=30)
    buf.feed("Some text")
    buf.flush()
    assert buf.flush() == ""


def test_exclamation_and_question_marks():
    buf = SentenceBuffer(min_chars=10)
    result = buf.feed("Really? Yes! Okay.")
    assert "Really?" in result
    assert "Yes!" in result
    assert "Okay." in result
