import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ReleasePackagingTest(unittest.TestCase):
    def test_every_runtime_service_is_selected_by_the_release_builder(self):
        with tempfile.TemporaryDirectory(prefix="qsou-compose-contract-") as directory:
            environment = {
                "PATH": os.environ["PATH"],
                "DOCKER_CONFIG": directory,
                "COMPOSE_DISABLE_ENV_FILE": "1",
                "DATABASE_URL": "postgresql://placeholder:placeholder@database/qsou",
                "QSOU_SECRET_KEY": "compose-contract-placeholder",
                "QSOU_ADMIN_USERNAME": "compose-contract",
                "QSOU_ADMIN_PASSWORD": "compose-contract-placeholder",
            }
            result = subprocess.run(
                ["docker", "compose", "--env-file", "/dev/null", "-f",
                 str(PROJECT_ROOT / "compose.yml"), "config", "--format", "json"],
                cwd=PROJECT_ROOT, env=environment, check=True, capture_output=True, text=True,
            )
        services = json.loads(result.stdout)["services"]
        expected = {"api", "collector", "elasticsearch", "indexer", "web"}
        self.assertEqual(set(services), expected)
        self.assertEqual(
            {name for name, service in services.items() if service.get("build")},
            expected,
            "Every runtime service must enter the existing build-service bundle selector",
        )
        for name, service in services.items():
            with self.subTest(service=name):
                self.assertEqual(service["restart"], "unless-stopped")
                self.assertEqual(service["platform"], "linux/amd64")


if __name__ == "__main__":
    unittest.main()
