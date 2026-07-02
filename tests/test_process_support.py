# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import os
import unittest

from host.process_support import preserved_stdio_flags


class ProcessSupportTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "POSIX file flags required")
    def test_preserved_stdio_flags_restores_nonblocking_state(self) -> None:
        import fcntl

        read_descriptor, write_descriptor = os.pipe()
        read_stream = os.fdopen(read_descriptor, "rb")
        write_stream = os.fdopen(write_descriptor, "wb")
        try:
            original = fcntl.fcntl(write_descriptor, fcntl.F_GETFL)
            with preserved_stdio_flags((write_stream,)):
                fcntl.fcntl(
                    write_descriptor,
                    fcntl.F_SETFL,
                    original | os.O_NONBLOCK,
                )
            restored = fcntl.fcntl(write_descriptor, fcntl.F_GETFL)
            self.assertEqual(restored, original)
        finally:
            read_stream.close()
            write_stream.close()
