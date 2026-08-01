"""Dependency-free request validation helpers for Moeen sync endpoints."""

MAX_SYNC_REQUEST_BYTES = 6 * 1024 * 1024
MAX_SYNC_CIPHERTEXT_CHARS = 5 * 1024 * 1024
MAX_SYNC_IV_CHARS = 256
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_AUDIO_IV_CHARS = 256


def content_length_exceeds(content_length, limit):
    return content_length is not None and content_length > limit


def valid_encrypted_state(ciphertext, iv):
    return (
        isinstance(ciphertext, str)
        and isinstance(iv, str)
        and 0 < len(ciphertext) <= MAX_SYNC_CIPHERTEXT_CHARS
        and 0 < len(iv) <= MAX_SYNC_IV_CHARS
    )


def valid_audio_metadata(audio_id, iv):
    return (
        isinstance(audio_id, str)
        and 0 < len(audio_id) <= 120
        and isinstance(iv, str)
        and 0 < len(iv) <= MAX_AUDIO_IV_CHARS
    )
