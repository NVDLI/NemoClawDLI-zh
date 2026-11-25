"""Regression checks for the Chinese contribution and dual-license contract."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "chinese_contribution_audit", ROOT / "scripts/validation/contribution_safety_audit.py"
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ChineseContributionContract(unittest.TestCase):
    def codes(self, path, text):
        return {item['code'] for item in AUDIT.audit_repo(ROOT, text_overrides={path: text})}

    def test_reviewed_chinese_baseline(self):
        self.assertEqual([], AUDIT.audit_repo(ROOT))

    def test_cla_removal_and_reversal(self):
        path = 'CONTRIBUTING.md'
        text = (ROOT / path).read_text(encoding='utf-8')
        clause = '无需另行签署贡献者许可协议（CLA）。'
        self.assertIn(clause, text)
        for replacement in ['', '必须另行签署贡献者许可协议（CLA）。']:
            with self.subTest(replacement=replacement):
                self.assertIn('cla-applicability', self.codes(path, text.replace(clause, replacement)))

    def test_readme_controls_cannot_be_removed(self):
        path = 'README.md'
        text = (ROOT / path).read_text(encoding='utf-8')
        for clause, code in [
            ('任何贡献者、维护者或智能体都不能审批自己提交的受保护合并或版本发布。', 'independent-review'),
            ('人工审批不能替代缺失的控制措施，也不能消除尚未验证的发布风险。', 'approval-not-control'),
        ]:
            self.assertIn(clause, text)
            self.assertIn(code, self.codes(path, text.replace(clause, '')))

    def test_license_body_changes_are_detected(self):
        text = (ROOT / 'LICENSE').read_text(encoding='utf-8')
        self.assertIn('root-license', self.codes('LICENSE', text + '\nUnauthorized license addition.\n'))

    def test_internal_body_not_required_or_allowed_in_public_guidance(self):
        for path in ['README.md', 'CONTRIBUTING.md', 'docs/release_playbook.md']:
            text = (ROOT / path).read_text(encoding='utf-8')
            self.assertIn('public-review-privacy', self.codes(path, text + '\nOSRB\n'))

    def test_publication_remains_blocked(self):
        self.assertTrue(AUDIT.audit_publication_approval(ROOT))


if __name__ == '__main__':
    unittest.main()
