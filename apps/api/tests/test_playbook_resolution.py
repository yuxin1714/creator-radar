import unittest
from unittest.mock import Mock
from types import SimpleNamespace

from app.providers.base import ProviderError
from app.services.creation_playbooks import resolve_playbook


class PlaybookResolutionTests(unittest.TestCase):
    def test_builtin_loads_complete_rules(self):
        db = Mock()
        db.get.return_value = None
        revision, content = resolve_playbook(db, "structure-borrowing-v1")
        self.assertEqual(revision, "1.0")
        self.assertIn("rules", content)
        self.assertIn("平台", content)

    def test_missing_remote_content_fails_closed(self):
        db = Mock()
        db.get.side_effect = [SimpleNamespace(status="ACTIVE", revision="new"), None]
        with self.assertRaises(ProviderError) as raised:
            resolve_playbook(db, "remote")
        self.assertEqual(raised.exception.code, "playbook_not_synced")

    def test_generation_uses_pinned_revision_after_sync(self):
        db = Mock()
        db.get.side_effect = [SimpleNamespace(status="ACTIVE", revision="new"), SimpleNamespace(revision="old", content="Original rules")]
        self.assertEqual(resolve_playbook(db, "remote", "old"), ("old", "Original rules"))
        self.assertEqual(db.get.call_args.args[1], "remote:old")

    def test_unknown_skill_does_not_fall_back(self):
        db = Mock()
        db.get.return_value = None
        with self.assertRaises(ProviderError):
            resolve_playbook(db, "missing")
