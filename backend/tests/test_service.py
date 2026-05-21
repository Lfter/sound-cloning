import csv
import tempfile
import unittest
from pathlib import Path

from backend.app.service import VoiceStudioService
from helpers import create_voice, make_paths


class ServiceTests(unittest.TestCase):
    def test_create_voice_generate_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = VoiceStudioService(make_paths(root))
            voice = create_voice(service, root)
            project = service.create_project("Test Project")
            project = service.save_script(
                project["id"],
                "第一句需要补录。\n第二句也需要补录。",
                voice_id=voice["id"],
                controls={"variants": 2, "speed": 1.0},
            )

            job = service.jobs.create(project["id"])
            service._run_generation_job(job.id, [])
            job_status = service.get_job(job.id)
            self.assertEqual(job_status["status"], "done")
            self.assertEqual(len(job_status["clipIds"]), 4)

            export = service.export_project(project["id"])
            self.assertEqual(export["count"], 2)
            self.assertTrue(Path(export["manifestPath"]).exists())

    def test_save_script_replaces_stale_lines_and_clips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = VoiceStudioService(make_paths(root))
            voice = create_voice(service, root)
            project = service.create_project("Rewrite Project")
            project = service.save_script(project["id"], "旧的一句。", voice_id=voice["id"], controls={"variants": 2})
            job = service.jobs.create(project["id"])
            service._run_generation_job(job.id, [])
            self.assertEqual(len(service.db.query_all("SELECT * FROM clips")), 2)

            project = service.save_script(project["id"], "新的唯一一句。", voice_id=voice["id"], controls={"variants": 1})

            self.assertEqual([line["text"] for line in project["lines"]], ["新的唯一一句。"])
            self.assertEqual(service.db.query_all("SELECT * FROM clips"), [])

    def test_update_script_line_merges_and_clamps_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = VoiceStudioService(make_paths(root))
            voice = create_voice(service, root)
            project = service.create_project("Controls Project")
            project = service.save_script(
                project["id"],
                "需要调参的一句。",
                voice_id=voice["id"],
                controls={"speed": 1.1, "gainDb": -3, "variants": 2},
            )

            updated = service.update_script_line(
                project["lines"][0]["id"],
                controls={
                    "speed": 99,
                    "pitchSemitones": -99,
                    "pauseMs": 9999,
                    "seed": "",
                    "emotionHint": "x" * 200,
                },
            )

            self.assertEqual(updated["controls"]["speed"], 1.75)
            self.assertEqual(updated["controls"]["pitchSemitones"], -6.0)
            self.assertEqual(updated["controls"]["gainDb"], -3.0)
            self.assertEqual(updated["controls"]["variants"], 2)
            self.assertEqual(updated["controls"]["pauseMs"], 2000)
            self.assertIsNone(updated["controls"]["seed"])
            self.assertEqual(len(updated["controls"]["emotionHint"]), 160)

    def test_select_clip_controls_export_manifest_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = VoiceStudioService(make_paths(root))
            voice = create_voice(service, root)
            project = service.create_project("Export Project")
            project = service.save_script(project["id"], "导出时应该选第二版。", voice_id=voice["id"], controls={"variants": 2})
            job = service.jobs.create(project["id"])
            service._run_generation_job(job.id, [])

            project = service.get_project(project["id"])
            second_clip = project["lines"][0]["clips"][1]
            service.select_clip(second_clip["id"])
            export = service.export_project(project["id"], "客户/交付:*")

            with Path(export["manifestPath"]).open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(export["count"], 1)
            self.assertEqual(rows[0]["variant"], "2")
            self.assertTrue(Path(export["files"][0]).exists())

    def test_export_project_uses_unique_folder_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = VoiceStudioService(make_paths(root))
            voice = create_voice(service, root)
            project = service.create_project("Export Collision")
            project = service.save_script(project["id"], "同名导出不应该覆盖。", voice_id=voice["id"], controls={"variants": 1})
            job = service.jobs.create(project["id"])
            service._run_generation_job(job.id, [])

            first = service.export_project(project["id"], "fixed-name")
            second = service.export_project(project["id"], "fixed-name")

            self.assertNotEqual(first["exportDir"], second["exportDir"])
            self.assertTrue(Path(first["manifestPath"]).exists())
            self.assertTrue(Path(second["manifestPath"]).exists())

    def test_generation_job_reports_missing_voice_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = VoiceStudioService(make_paths(root))
            project = service.create_project("Broken Project")
            service.save_script(project["id"], "没有声音也不能静默成功。", controls={"variants": 1})

            job = service.jobs.create(project["id"])
            service._run_generation_job(job.id, [])
            status = service.get_job(job.id)

            self.assertEqual(status["status"], "error")
            self.assertEqual(status["progress"], 0)
            self.assertIn("No voice selected", status["errors"][0])


if __name__ == "__main__":
    unittest.main()
