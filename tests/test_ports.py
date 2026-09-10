import tempfile
import unittest
from pathlib import Path

from hub import ports


class PortTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_token_lookup(self):
        port = ports.create("Studio Bot", adapter="mock", data_dir=self.root)
        self.assertEqual(port["id"], "p_studio-bot")
        self.assertTrue(port["token"].startswith("gch_"))
        found = ports.find_by_token(port["token"], self.root)
        self.assertEqual(found["id"], port["id"])

    def test_revoke_rotates_token(self):
        port = ports.create("x", adapter="mock", data_dir=self.root)
        old = port["token"]
        ports.revoke("p_x", self.root)
        self.assertIsNone(ports.find_by_token(old, self.root))

    def test_public_view_hides_aga_token(self):
        port = ports.create("x", adapter="agensis", data_dir=self.root)
        ports.set_adapter_config("p_x", {"token": "aga_SUPERSECRETTOKEN99"}, self.root)
        view = ports.public_view(ports.get("p_x", self.root))
        self.assertNotIn("SUPERSECRET", str(view))


if __name__ == "__main__":
    unittest.main()
