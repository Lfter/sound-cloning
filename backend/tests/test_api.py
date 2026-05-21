import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app import main as api_module
from helpers import create_voice, make_service, write_reference


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = make_service(self.root)
        self.original_service = api_module.service
        api_module.service = self.service
        self.client = TestClient(api_module.app)

    def tearDown(self):
        api_module.service = self.original_service
        self.tmp.cleanup()

    @property
    def root(self):
        from pathlib import Path

        return Path(self.tmp.name)

    def test_health_and_model_status_use_isolated_service(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["ok"])
        self.assertEqual(health.json()["model"]["backend"], "preview")

        model = self.client.get("/model-status")
        self.assertEqual(model.status_code, 200)
        self.assertFalse(model.json()["available"])

    def test_project_routes_save_script_and_report_missing_project(self):
        created = self.client.post("/projects", json={"name": "API Project"})
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]

        saved = self.client.put(
            f"/projects/{project_id}/script",
            json={"text": "第一句。\n第二句。", "controls": {"variants": 2}},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(len(saved.json()["lines"]), 2)
        self.assertEqual(saved.json()["lines"][0]["controls"]["variants"], 2)

        missing = self.client.get("/projects/not-found")
        self.assertEqual(missing.status_code, 404)

    def test_voice_upload_and_clip_audio_route(self):
        reference = write_reference(self.root / "api-reference.wav")
        with reference.open("rb") as handle:
            response = self.client.post(
                "/voices",
                data={
                    "name": "API Voice",
                    "referenceText": "这是一段授权参考音频。",
                    "language": "Chinese",
                    "consentNote": "test",
                    "trimStartMs": "0",
                    "trimDurationMs": "2000",
                },
                files={"file": ("reference.wav", handle.read(), "audio/wav")},
            )
        self.assertEqual(response.status_code, 200)
        voice_id = response.json()["id"]

        project = self.client.post("/projects", json={"name": "Audio API"}).json()
        self.client.put(
            f"/projects/{project['id']}/script",
            json={"text": "需要试听的一句。", "voiceId": voice_id, "controls": {"variants": 1}},
        )
        job = self.service.jobs.create(project["id"])
        self.service._run_generation_job(job.id, [])
        refreshed = self.service.get_project(project["id"])
        clip_id = refreshed["lines"][0]["clips"][0]["id"]

        audio = self.client.get(f"/clips/{clip_id}/audio")
        self.assertEqual(audio.status_code, 200)
        self.assertEqual(audio.content[:4], b"RIFF")


if __name__ == "__main__":
    unittest.main()
