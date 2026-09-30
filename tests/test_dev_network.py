"""
Tests for dev_network.py. Not meant for students.
"""
import itertools
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import dev_network
from tests.helpers import split_like_dev_network


@pytest.fixture
def v6_commands(monkeypatch):
    """Record the 'v6' commands instead of running them."""
    commands = []
    monkeypatch.setattr(dev_network, "run_v6", commands.append)
    monkeypatch.setattr(dev_network, "check_docker", lambda: None)
    monkeypatch.setattr(dev_network, "remove_locked_node_logs", lambda: None)
    return commands


def test_environment_uses_the_v6_of_this_python():
    path = dev_network.get_environment()["PATH"]
    assert path.split(dev_network.os.pathsep)[0] == str(Path(sys.executable).parent)


@pytest.mark.parametrize("docker_host", [
    "unix:///var/run/docker.sock",                    # Docker Engine on Linux
    "unix:///Users/student/.docker/run/docker.sock",  # Docker Desktop on macOS
    "npipe:////./pipe/dockerDesktopLinuxEngine",      # Docker Desktop on Windows
])
def test_environment_uses_the_docker_of_the_current_context(monkeypatch, docker_host):
    """'v6' does not know Docker contexts, so it must be told which Docker the 'docker' command uses."""
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setattr(dev_network.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(dev_network.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout=docker_host + "\n"))
    assert dev_network.get_environment()["DOCKER_HOST"] == docker_host


def test_environment_keeps_your_own_docker_host(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://127.0.0.1:2375")
    assert dev_network.get_environment()["DOCKER_HOST"] == "tcp://127.0.0.1:2375"


def test_environment_without_docker(monkeypatch):
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setattr(dev_network.shutil, "which", lambda name: None)
    assert "DOCKER_HOST" not in dev_network.get_environment()


@pytest.mark.parametrize("system, context, expected_url", [
    ("Windows", "", "http://host.docker.internal"),
    ("Darwin", "", "http://host.docker.internal"),
    ("Linux", "desktop-linux\n", "http://host.docker.internal"),
    ("Linux", "default\n", "http://172.17.0.1"),
])
def test_server_url(monkeypatch, system, context, expected_url):
    monkeypatch.setattr(dev_network.platform, "system", lambda: system)
    monkeypatch.setattr(dev_network.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=context))
    assert dev_network.get_server_url() == expected_url


def test_start_creates_the_network_the_first_time(monkeypatch, v6_commands):
    monkeypatch.setattr(dev_network, "network_exists", lambda: False)
    monkeypatch.setattr(dev_network, "get_server_url", lambda: "http://172.17.0.1")

    dev_network.start()

    create, start = v6_commands
    assert create[:2] == ["dev", "create-demo-network"]
    assert create[create.index("--name") + 1] == dev_network.NETWORK_NAME
    assert create[create.index("--num-nodes") + 1] == str(dev_network.NUMBER_OF_NODES)
    assert create[create.index("--server-url") + 1] == "http://172.17.0.1"
    dataset = create.index("--add-dataset")
    assert create[dataset + 1] == "survival"
    # A shuffled copy of the data is used, with the same name (and so the same label)
    assert Path(create[dataset + 2]).name == "survival.csv"
    assert Path(create[dataset + 2]).parent != dev_network.SYNTHETIC_DATA_FOLDER
    assert create[create.index("--image") + 1] == dev_network.IMAGES["server"]
    assert create[create.index("--ui-image") + 1] == dev_network.IMAGES["ui"]
    assert start == START_COMMAND


START_COMMAND = ["dev", "start-demo-network", "--name", dev_network.NETWORK_NAME,
                 "--server-image", dev_network.IMAGES["server"],
                 "--node-image", dev_network.IMAGES["node"],
                 "--store-image", dev_network.IMAGES["algorithm-store"]]


def test_start_only_starts_an_existing_network(monkeypatch, v6_commands):
    monkeypatch.setattr(dev_network, "network_exists", lambda: True)
    dev_network.start()
    assert v6_commands == [START_COMMAND]


@pytest.mark.parametrize("stop_creating", [SystemExit("failed"), KeyboardInterrupt()])
def test_half_created_network_is_removed(monkeypatch, v6_commands, stop_creating):
    """Otherwise the next start skips creating the network and uses a server without users."""
    def run_v6(arguments):
        v6_commands.append(arguments)
        if arguments[1] == "create-demo-network":
            monkeypatch.setattr(dev_network, "network_exists", lambda: True)
            raise stop_creating
    monkeypatch.setattr(dev_network, "run_v6", run_v6)
    monkeypatch.setattr(dev_network, "network_exists", lambda: False)
    monkeypatch.setattr(dev_network, "get_server_url", lambda: "http://172.17.0.1")

    with pytest.raises(type(stop_creating)):
        dev_network.start()

    assert [command[1] for command in v6_commands] == [
        "create-demo-network", "stop-demo-network", "remove-demo-network"]


def test_failed_creation_without_files_removes_nothing(monkeypatch, v6_commands):
    def run_v6(arguments):
        v6_commands.append(arguments)
        raise SystemExit("failed")
    monkeypatch.setattr(dev_network, "run_v6", run_v6)
    monkeypatch.setattr(dev_network, "network_exists", lambda: False)
    monkeypatch.setattr(dev_network, "get_server_url", lambda: "http://172.17.0.1")

    with pytest.raises(SystemExit):
        dev_network.start()

    assert [command[1] for command in v6_commands] == ["create-demo-network"]


def test_images_use_the_same_version_as_the_requirements():
    requirements = (dev_network.Path(dev_network.__file__).parent / "requirements.txt").read_text()
    assert f"vantage6=={dev_network.VANTAGE6_VERSION}" in requirements
    assert all(image.endswith(f":{dev_network.VANTAGE6_VERSION}") for image in dev_network.IMAGES.values())


def test_stop(v6_commands):
    dev_network.stop()
    assert v6_commands == [["dev", "stop-demo-network", "--name", dev_network.NETWORK_NAME]]


def test_remove(monkeypatch, v6_commands):
    """'v6 dev remove-demo-network' does nothing while the server runs, so the network is stopped first."""
    monkeypatch.setattr(dev_network, "network_exists", lambda: True)
    dev_network.remove()
    assert v6_commands == [["dev", "stop-demo-network", "--name", dev_network.NETWORK_NAME],
                           ["dev", "remove-demo-network", "--name", dev_network.NETWORK_NAME]]


def test_remove_without_network(monkeypatch, v6_commands, capsys):
    monkeypatch.setattr(dev_network, "network_exists", lambda: False)
    dev_network.remove()
    assert v6_commands == []
    assert "no developer network" in capsys.readouterr().out


def test_warning_for_small_data_sets(tmp_path, capsys):
    small_file = tmp_path / "small.csv"
    small_file.write_text("age\n" + "30\n" * 100)
    dev_network.check_number_of_records(small_file)
    assert "only 33 records" in capsys.readouterr().out


def test_no_warning_for_the_survival_data(capsys):
    dev_network.check_number_of_records(dev_network.SYNTHETIC_DATA_FOLDER / "survival.csv")
    assert capsys.readouterr().out == ""


def test_docker_missing(monkeypatch):
    monkeypatch.setattr(dev_network.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit, match="Docker is not installed"):
        dev_network.check_docker()


def test_docker_without_permission(monkeypatch):
    monkeypatch.setattr(dev_network.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(dev_network.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stderr="permission denied while trying to connect to the Docker daemon socket"))
    with pytest.raises(SystemExit, match="docker' group"):
        dev_network.check_docker()


def test_failing_v6_command_stops_the_script(monkeypatch):
    monkeypatch.setattr(dev_network.shutil, "which", lambda name, path=None: "/usr/bin/v6")
    monkeypatch.setattr(dev_network.subprocess, "run",
                        lambda *args, **kwargs: subprocess.CompletedProcess(args, returncode=1))
    with pytest.raises(SystemExit, match="did not finish correctly"):
        dev_network.run_v6(["dev", "start-demo-network"])


def test_network_exists_uses_the_vantage6_configuration(monkeypatch):
    pytest.importorskip("vantage6.cli")
    from vantage6.cli.context.server import ServerContext
    monkeypatch.setattr(ServerContext, "config_exists",
                        classmethod(lambda cls, name, system_folders: name == dev_network.NETWORK_NAME))
    assert dev_network.network_exists()


def test_remove_locked_node_logs(monkeypatch, tmp_path):
    """Log files that the user cannot write to (made by the root user in a container) are removed."""
    pytest.importorskip("vantage6.cli")
    from vantage6.cli.context.node import NodeContext
    monkeypatch.setattr(NodeContext, "instance_folders",
                        classmethod(lambda cls, instance_type, name, system_folders: {"log": tmp_path / name}))
    log_folder = tmp_path / f"{dev_network.NETWORK_NAME}_node_1"
    log_folder.mkdir()
    locked, writable = log_folder / "node_user.log", log_folder / "other.log"
    locked.write_text("written by the container")
    writable.write_text("written by the user")
    monkeypatch.setattr(dev_network.os, "access", lambda path, mode: Path(path) != locked)

    dev_network.remove_locked_node_logs()

    assert not locked.exists() and writable.exists()


def hospitals_per_node(csv_file):
    """The hospital (first letter of the patient ID) of each node, as the developer network splits the file."""
    nodes = split_like_dev_network(pd.read_csv(csv_file), dev_network.NUMBER_OF_NODES)
    return tuple("".join(sorted(set(node["id"].str[0]))) for node in nodes)


def test_shuffle_hospitals_keeps_every_hospital_together(tmp_path):
    original = dev_network.SYNTHETIC_DATA_FOLDER / "survival.csv"
    shuffled = dev_network.shuffle_hospitals(original, tmp_path)

    assert shuffled.name == original.name
    # Every node still receives exactly one complete hospital
    assert sorted(hospitals_per_node(shuffled)) == ["A", "B", "C"]
    original_data, shuffled_data = pd.read_csv(original), pd.read_csv(shuffled)
    assert list(shuffled_data.columns) == list(original_data.columns)
    for hospital in "ABC":
        pd.testing.assert_frame_equal(
            original_data[original_data["id"].str[0] == hospital].reset_index(drop=True),
            shuffled_data[shuffled_data["id"].str[0] == hospital].reset_index(drop=True))


def test_shuffle_hospitals_gives_the_different_coding_to_any_organisation(tmp_path):
    """Hospital C (with the T sub-stages) must be able to end up at every node, in every possible order."""
    original = dev_network.SYNTHETIC_DATA_FOLDER / "survival.csv"
    orders = set()
    for seed in range(50):
        dev_network.random.seed(seed)
        orders.add(hospitals_per_node(dev_network.shuffle_hospitals(original, tmp_path)))
    assert orders == set(itertools.permutations("ABC"))
