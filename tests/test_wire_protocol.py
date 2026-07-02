# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

from wire_protocol import (FLAG_ACK, Frame, ProtocolError, StreamDecoder,  # noqa: E402
                           decode_frame, encode_frame)


class WireProtocolTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        frame = Frame(0x12, FLAG_ACK, 17, b"payload")
        self.assertEqual(decode_frame(encode_frame(frame)), frame)

    def test_crc_rejects_corruption(self) -> None:
        encoded = bytearray(encode_frame(Frame(1, 0, 1, b"abc")))
        encoded[-1] ^= 1
        with self.assertRaisesRegex(ProtocolError, "CRC-32"):
            decode_frame(bytes(encoded))

    def test_stream_decoder_resynchronizes(self) -> None:
        first = encode_frame(Frame(1, 0, 1, b"a"))
        second = encode_frame(Frame(2, 0, 2, b"bc"))
        decoder = StreamDecoder()
        self.assertEqual(decoder.feed(b"noise" + first[:7]), [])
        frames = decoder.feed(first[7:] + second)
        self.assertEqual([frame.sequence for frame in frames], [1, 2])


if __name__ == "__main__":
    unittest.main()
