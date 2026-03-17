import sys
from pathlib import Path

import pytest  # type: ignore

sys.path.insert(0, str(Path(__file__).parent.parent))


class FakeStat:
    def __init__(self, size):
        self.st_size = size


class FakeArtifactoryPath:
    files: dict[str, int] = {}

    def __init__(self, path, auth=None):
        self.path = path

    def __str__(self):
        return self.path

    def __truediv__(self, other):
        return FakeArtifactoryPath(f"{self.path}/{other}")

    def rglob(self, pattern):
        for p in self.files:
            if p.startswith(self.path):
                yield FakeArtifactoryPath(p)

    def relative_to(self, other):
        return Path(self.path).relative_to(other.path)

    def is_dir(self):
        return False

    def stat(self):
        return FakeStat(self.files.get(self.path, 10))


@pytest.fixture
def fake_artifactory(monkeypatch):
    from arty_mc.core import transfers  # type: ignore

    monkeypatch.setattr(transfers, "ArtifactoryPath", FakeArtifactoryPath)
    FakeArtifactoryPath.files = {}
    return FakeArtifactoryPath
