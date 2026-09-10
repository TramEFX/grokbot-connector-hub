import tempfile
import time
import unittest
from pathlib import Path

from hub import mailbox


class MailboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_put_list_reply(self):
        mailbox.put("p_a", {"id": "job-1", "prompt": "hello", "budget_seconds": 30}, self.root)
        open_jobs = mailbox.list_open("p_a", self.root)
        self.assertEqual(len(open_jobs), 1)
        self.assertEqual(open_jobs[0]["prompt"], "hello")
        record = mailbox.reply("p_a", "job-1", "hi back", self.root)
        self.assertEqual(record["status"], "replied")
        self.assertEqual(mailbox.list_open("p_a", self.root), [])

    def test_rejects_path_job_id(self):
        with self.assertRaises(mailbox.MailboxError):
            mailbox.put("p_a", {"id": "../etc/passwd", "prompt": "x"}, self.root)

    def test_empty_reply_rejected(self):
        mailbox.put("p_a", {"id": "job-2", "prompt": "x"}, self.root)
        with self.assertRaises(mailbox.MailboxError):
            mailbox.reply("p_a", "job-2", "   ", self.root)

    def test_expire(self):
        mailbox.put(
            "p_a",
            {"id": "old", "prompt": "x", "deadline_at": time.time() - 1},
            self.root,
        )
        expired = mailbox.expire_open("p_a", self.root)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
