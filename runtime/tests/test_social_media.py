from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.core.dispatch import CanonicalTaskDispatcher
from runtime.core.jobs import JobRuntime
from runtime.core.references import CanonicalReferenceResolver
from runtime.providers.config import ProviderConfiguration


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOCIAL_SKILLS = (
    "content-calendar",
    "post-planner",
    "caption-writer",
    "hook-generator",
    "content-repurpose",
    "competitor-monitor",
    "performance-review",
    "comment-analysis",
    "weekly-social-report",
)


class SocialMediaRoutingTests(unittest.TestCase):
    def test_a_task_class_dispatches_to_social_media_chain(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = JobRuntime(Path(root) / "jobs")
            job = CanonicalTaskDispatcher(runtime, REPOSITORY_ROOT).dispatch(
                task="Plan next week's Instagram content",
                task_class="social_media",
                created_by="social-media-routing-test",
                input_refs=[],
                approval_reason="test only",
                request_approval=False,
            )

        self.assertEqual(job["task_class"], "social_media")
        self.assertEqual(job["agent"], "social-media")
        self.assertEqual(job["workflow"], "social-media")
        self.assertEqual(job["capability"], "social_media_content")

    def test_b_social_scenario_routes_resolve_canonical_references(self) -> None:
        scenarios = {
            "Plan next week's Instagram content": "content-calendar",
            "Write a caption for this Reel": "caption-writer",
            "Give me five hook ideas for this video": "hook-generator",
            "Turn this blog post into LinkedIn and Instagram drafts": "content-repurpose",
            "Analyze comments and identify recurring themes": "comment-analysis",
            "Review the performance of this Reel": "performance-review",
            "Analyze competitor Instagram posting patterns": "competitor-monitor",
            "Publish this post now": "post-planner",
        }
        resolver = CanonicalReferenceResolver(REPOSITORY_ROOT)

        for prompt, skill in scenarios.items():
            with self.subTest(prompt=prompt):
                refs = resolver.resolve(
                    {
                        "agent": "social-media",
                        "skill": skill,
                        "workflow": "social-media",
                        "capability": "social_media_content",
                        "project_id": None,
                    }
                )
                paths = {ref["ref"] for ref in refs}
                self.assertIn("agents/social-media/ROLE.md", paths)
                self.assertIn(f"skills/social-media/{skill}/SKILL.md", paths)
                self.assertIn("orchestrator/workflows/social-media.yaml", paths)
                self.assertIn("orchestrator/routing/capabilities.yaml", paths)

    def test_c_brand_positioning_remains_marketing(self) -> None:
        refs = CanonicalReferenceResolver(REPOSITORY_ROOT).resolve(
            {
                "agent": "marketing",
                "skill": None,
                "workflow": "marketing",
                "capability": "marketing_analysis",
                "project_id": None,
            }
        )
        paths = {ref["ref"] for ref in refs}
        self.assertIn("agents/marketing/ROLE.md", paths)
        self.assertNotIn("agents/social-media/ROLE.md", paths)

    def test_d_every_social_skill_is_resolvable_and_complete(self) -> None:
        required_headings = (
            "## Purpose",
            "## Inputs",
            "## Outputs",
            "## Constraints",
            "## Procedure",
            "## Approval Boundaries",
            "## Completion Checks",
        )
        resolver = CanonicalReferenceResolver(REPOSITORY_ROOT)

        for skill in SOCIAL_SKILLS:
            with self.subTest(skill=skill):
                refs = resolver.resolve(
                    {
                        "agent": "social-media",
                        "skill": skill,
                        "workflow": "social-media",
                        "capability": "social_media_content",
                        "project_id": None,
                    }
                )
                skill_ref = next(
                    ref for ref in refs if ref["ref"].endswith(f"/{skill}/SKILL.md")
                )
                content = (REPOSITORY_ROOT / skill_ref["ref"]).read_text(
                    encoding="utf-8"
                )
                for heading in required_headings:
                    self.assertIn(heading, content)
                lowered = content.casefold()
                for project_specific_name in (
                    "brightshore",
                    "instagram",
                    "youtube",
                    "codebar",
                ):
                    self.assertNotIn(project_specific_name, lowered)

    def test_e_both_providers_are_neutrally_eligible(self) -> None:
        configuration = ProviderConfiguration(REPOSITORY_ROOT)

        self.assertTrue(configuration.eligible("claude", "social_media_content"))
        self.assertTrue(configuration.eligible("codex", "social_media_content"))
        self.assertEqual(configuration.weight("claude", "social_media_content"), 50)
        self.assertEqual(configuration.weight("codex", "social_media_content"), 50)

    def test_f_publication_is_unimplemented_and_approval_gated(self) -> None:
        workflow = (
            REPOSITORY_ROOT / "orchestrator" / "workflows" / "social-media.yaml"
        ).read_text(encoding="utf-8")

        self.assertNotIn("\nconnectors:", workflow)
        self.assertIn("future_connectors:", workflow)
        for action in (
            "publish_post",
            "edit_published_post",
            "delete_published_post",
            "send_public_reply",
            "modify_paid_campaign",
            "spend_budget",
            "alter_account_settings",
        ):
            self.assertIn(f"  - {action}", workflow)


if __name__ == "__main__":
    unittest.main()
