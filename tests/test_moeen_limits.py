import unittest

from moeen_limits import MAX_AUDIO_BYTES, MAX_SYNC_REQUEST_BYTES, content_length_exceeds, valid_audio_metadata, valid_encrypted_state


class MoeenRequestLimitTests(unittest.TestCase):
    def test_unknown_or_exact_content_length_is_allowed(self):
        self.assertFalse(content_length_exceeds(None, MAX_AUDIO_BYTES))
        self.assertFalse(content_length_exceeds(MAX_AUDIO_BYTES, MAX_AUDIO_BYTES))

    def test_oversized_content_length_is_rejected(self):
        self.assertTrue(content_length_exceeds(MAX_SYNC_REQUEST_BYTES + 1, MAX_SYNC_REQUEST_BYTES))

    def test_encrypted_state_requires_bounded_strings(self):
        self.assertTrue(valid_encrypted_state("ciphertext", "iv"))
        self.assertFalse(valid_encrypted_state([], "iv"))
        self.assertFalse(valid_encrypted_state("ciphertext", ""))

    def test_audio_metadata_is_bounded(self):
        self.assertTrue(valid_audio_metadata("audio-id", "iv"))
        self.assertFalse(valid_audio_metadata("x" * 121, "iv"))
        self.assertFalse(valid_audio_metadata("audio-id", "x" * 257))


if __name__ == "__main__":
    unittest.main()
