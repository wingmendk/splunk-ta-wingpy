import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_ta


class ReleaseMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        for name in (*build_ta.REQUIRED_TA_FILES, *build_ta.LICENSE_FILES):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(build_ta.REPO_ROOT / name, destination)
        self.manifest_path = self.root / "app.manifest"
        self.app_conf_path = self.root / "default" / "app.conf"
        paths = patch.multiple(
            build_ta,
            REPO_ROOT=self.root,
            TA_SOURCE_DIR=self.root,
            APP_MANIFEST_PATH=self.manifest_path,
            APP_CONF_PATH=self.app_conf_path,
        )
        paths.start()
        self.addCleanup(paths.stop)

    def test_rejects_unsupported_forwarder_workloads(self) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        for workload in ("_universal_forwarders", "_heavy_forwarders"):
            with self.subTest(workload=workload):
                manifest["targetWorkloads"] = [workload]
                self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "targetWorkloads"):
                    build_ta.validate_source_metadata()

    def test_rejects_disabled_update_checks(self) -> None:
        conf = self.app_conf_path.read_text(encoding="utf-8")
        self.app_conf_path.write_text(
            conf.replace("check_for_updates = true", "check_for_updates = false"),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            build_ta.validate_source_metadata()


if __name__ == "__main__":
    unittest.main()
