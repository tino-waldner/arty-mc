from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest  # type: ignore
import requests  # type: ignore
from artifactory import ArtifactoryException  # type: ignore

from arty_mc.core.api_client import ArtifactoryAPI  # type: ignore


@pytest.fixture
def config():
    return {
        "server": "https://fake.artifactory",
        "user": "fake_user",
        "token": "token",
    }


@pytest.fixture
def api(config):
    with patch("arty_mc.core.api_client.AuthSession"):
        return ArtifactoryAPI(config)


def make_child(name, is_dir=False, size=10, modified=None, props=None):
    child = MagicMock()
    child.name = name
    stat = MagicMock()
    stat.is_dir = is_dir
    stat.size = size
    stat.last_modified = modified
    child.stat.return_value = stat
    child.properties = props or {}

    return child


def test_api_client_init(config):
    with patch("arty_mc.core.api_client.AuthSession") as mock_session:
        api = ArtifactoryAPI(config)
        mock_session.assert_called_once()
        assert api.base_url == "https://fake.artifactory"
        assert api.apikey == "token"


@patch("arty_mc.core.api_client.ArtifactoryPath")
def test_list_folder_file(mock_path, api):
    child = make_child(
        "file.txt",
        is_dir=False,
        size=123,
        modified=datetime(2024, 1, 1, 12, 0, 0),
    )

    folder = MagicMock()
    folder.iterdir.return_value = [child]
    mock_path.return_value = folder
    result = api.list_folder("repo")

    assert result == [
        {
            "name": "file.txt",
            "is_dir": False,
            "size": 123,
            "modified": "2024-01-01 12:00:00",
        }
    ]


@patch("arty_mc.core.api_client.ArtifactoryPath")
def test_list_folder_directory(mock_path, api):
    child = make_child(
        "folder",
        is_dir=True,
        modified=None,
        props={"lastModified": "2024-01-01"},
    )

    folder = MagicMock()
    folder.iterdir.return_value = [child]
    mock_path.return_value = folder
    result = api.list_folder("repo")
    assert result[0]["name"] == "folder"
    assert result[0]["is_dir"] is True
    assert result[0]["size"] == "-"


@patch("arty_mc.core.api_client.ArtifactoryPath")
def test_list_folder_modified_from_properties(mock_path, api):
    child = make_child(
        "file2.txt",
        modified=None,
        props={"lastModified": "2024-01-02"},
    )

    folder = MagicMock()
    folder.iterdir.return_value = [child]
    mock_path.return_value = folder
    result = api.list_folder("repo")
    assert result[0]["name"] == "file2.txt"
    assert result[0]["size"] == 10


@patch("arty_mc.core.api_client.ArtifactoryPath")
def test_list_folder_artifactory_exception(mock_path, api):
    mock_path.side_effect = ArtifactoryException("boom")

    with pytest.raises(RuntimeError):
        api.list_folder("repo")


@patch("arty_mc.core.api_client.ArtifactoryPath")
def test_list_folder_request_exception(mock_path, api):
    mock_path.side_effect = requests.exceptions.RequestException("network")

    with pytest.raises(RuntimeError):
        api.list_folder("repo")


def test_list_folder_properties_exception(api):
    child = MagicMock()
    child.name = "file3.txt"
    stat = MagicMock()
    stat.is_dir = False
    stat.size = 50
    stat.last_modified = None
    child.stat.return_value = stat

    type(child).properties = property(lambda self: (_ for _ in ()).throw(Exception("props fail")))

    folder = MagicMock()
    folder.iterdir.return_value = [child]

    with patch("arty_mc.core.api_client.ArtifactoryPath", return_value=folder):
        result = api.list_folder("repo")

    assert result == [
        {
            "name": "file3.txt",
            "is_dir": False,
            "size": 50,
            "modified": None,
        }
    ]


def test_get_license_returns_license_field(config):
    with patch("arty_mc.core.api_client.AuthSession") as mock_session:
        api = ArtifactoryAPI(config)
        mock_session.return_value.get.return_value = {
            "version": "7.x",
            "license": "OSS",
        }
        api.session = mock_session.return_value
        assert api.get_license() == "OSS"


def test_get_license_cached(config):
    with patch("arty_mc.core.api_client.AuthSession") as mock_session:
        api = ArtifactoryAPI(config)
        mock_session.return_value.get.return_value = {"license": "Pro"}
        api.session = mock_session.return_value
        api.get_license()
        api.get_license()  # second call should NOT hit the network
        assert mock_session.return_value.get.call_count == 1


def test_get_license_returns_unknown_on_error(config):
    with patch("arty_mc.core.api_client.AuthSession") as mock_session:
        api = ArtifactoryAPI(config)
        mock_session.return_value.get.side_effect = Exception("network error")
        api.session = mock_session.return_value
        assert api.get_license() == "unknown"


def test_has_aql_false_for_oss(config):
    with patch("arty_mc.core.api_client.AuthSession") as mock_session:
        api = ArtifactoryAPI(config)
        mock_session.return_value.get.return_value = {"license": "OSS"}
        api.session = mock_session.return_value
        assert api.has_aql() is False


def test_has_aql_false_when_unknown(config):
    with patch("arty_mc.core.api_client.AuthSession") as mock_session:
        api = ArtifactoryAPI(config)
        mock_session.return_value.get.side_effect = Exception("unreachable")
        api.session = mock_session.return_value
        assert api.has_aql() is False


def test_has_aql_true_for_pro(config):
    with patch("arty_mc.core.api_client.AuthSession") as mock_session:
        api = ArtifactoryAPI(config)
        mock_session.return_value.get.return_value = {"license": "Pro"}
        api.session = mock_session.return_value
        assert api.has_aql() is True
