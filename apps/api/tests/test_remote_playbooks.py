import unittest
from unittest.mock import patch
from app.services.remote_playbooks import read_bundle, MAX_BYTES
from app.providers.base import ProviderError


class RemoteBundleTests(unittest.TestCase):
    def read(self, reference=True, symlink=False, oversized=False):
        main = b'---\nname: test\n---\n# Test\nUse `references/loop.md`.'
        tree = b'100644 blob a\tskill/SKILL.md\0'
        if reference:
            tree += (b'120000' if symlink else b'100644') + b' blob b\tskill/references/loop.md\0'
        def git(*args, **kwargs):
            if args[0] == 'ls-tree': return tree
            if args[:2] == ('cat-file', '-s'): return str(MAX_BYTES + 1 if oversized else 100).encode()
            return main if args[-1] == 'a' else b'# Loop\nRevise the weakest mechanism.'
        with patch('app.services.remote_playbooks.git', side_effect=git):
            return read_bundle('unused', 'skill/SKILL.md')

    def test_includes_reference_content(self):
        self.assertIn('Revise the weakest mechanism.', self.read())

    def test_missing_reference_is_rejected(self):
        with self.assertRaises(ProviderError): self.read(reference=False)

    def test_reference_symlink_is_rejected(self):
        with self.assertRaises(ProviderError): self.read(symlink=True)

    def test_size_checked_before_reading_blob(self):
        with self.assertRaises(ProviderError): self.read(oversized=True)

    def test_parent_path_is_rejected(self):
        with self.assertRaises(ProviderError): read_bundle('unused', '../SKILL.md')
