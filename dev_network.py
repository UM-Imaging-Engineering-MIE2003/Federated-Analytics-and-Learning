"""
Start, stop or remove the vantage6 developer network used in this course.

The developer network runs on your own computer. It contains one server, one
algorithm store, a web interface and three nodes (one node per organisation).
Each node receives one third of the example data sets.

Run this script from a terminal, not from the notebook:

    python dev_network.py start     # create (first time only) and start the network
    python dev_network.py stop      # stop the network, your data and settings are kept
    python dev_network.py remove    # delete the network completely

CSV files in the 'synthetic_datasets' folder are added to the nodes when the network is
created for the first time. Each file contains one block of rows per hospital; the blocks are
put in a random order first, so that every network gives the hospitals to different nodes.
If you add or change a file later, remove the network and start it again.

Docker must be installed and running before you start the network.
"""
import argparse
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Name of the developer network; the notebook does not need to know this name
NETWORK_NAME = "fal_demo"
NUMBER_OF_NODES = 3
SERVER_PORT = 7601

# Use exactly this version of vantage6 for the server, the nodes, the algorithm store and the
# web interface. Without this, 'v6 dev' downloads the newest version, and every student could
# end up with a different version. Keep it the same as the version in requirements.txt.
VANTAGE6_VERSION = "4.15.1"
IMAGES = {name: f"ghcr.io/vantage6/infrastructure/{name}:{VANTAGE6_VERSION}"
          for name in ["server", "node", "algorithm-store", "ui"]}

# Folder with extra CSV files that are added to the nodes (optional)
SYNTHETIC_DATA_FOLDER = Path(__file__).parent / "synthetic_datasets"

# The minimum number of records that each node should receive from a CSV file
MINIMUM_RECORDS_PER_NODE = 250


def get_environment() -> dict:
    """
    Make sure the 'v6' command of this Python environment is used, and that it can find Docker.

    'v6 dev start-demo-network' calls 'v6' again by itself, so the folder that
    contains 'v6' must be on the PATH, also when the environment is not activated.

    The 'docker' command finds Docker through the current Docker context, but 'v6' does not: it
    only looks at /var/run/docker.sock. On macOS, Docker Desktop (and also Colima and OrbStack)
    uses another file, for example ~/.docker/run/docker.sock, so 'v6' says that it cannot reach
    the Docker engine. Setting DOCKER_HOST tells 'v6' to use the same Docker as the 'docker' command.
    """
    environment = os.environ.copy()
    scripts_folder = str(Path(sys.executable).parent)
    environment["PATH"] = scripts_folder + os.pathsep + environment.get("PATH", "")
    if "DOCKER_HOST" not in environment and shutil.which("docker"):
        context = subprocess.run(["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
                                 capture_output=True, text=True)
        if context.returncode == 0 and context.stdout.strip():
            environment["DOCKER_HOST"] = context.stdout.strip()
    return environment


def run_v6(arguments: list[str]) -> None:
    """Run a 'v6' command and stop the script when it fails."""
    command = ["v6"] + arguments
    print(f"\n>>> {' '.join(command)}\n")
    environment = get_environment()
    executable = shutil.which("v6", path=environment["PATH"])
    if executable is None:
        sys.exit("Could not find the 'v6' command. "
                 "Did you install the requirements with 'pip install -r requirements.txt'?")
    result = subprocess.run([executable] + arguments, env=environment)
    if result.returncode != 0:
        sys.exit(f"The command '{' '.join(command)}' did not finish correctly. "
                 f"Please read the messages above.")


def check_docker() -> None:
    """Check that Docker is installed, running and usable without administrator rights."""
    if shutil.which("docker") is None:
        sys.exit("Docker is not installed. Please install Docker Desktop first.")
    result = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if result.returncode != 0:
        message = "Docker is not running, or you are not allowed to use it.\n"
        if "permission denied" in result.stderr.lower():
            message += ("On Linux, ask your administrator to add you to the 'docker' group:\n"
                        "    sudo usermod -aG docker $USER\n"
                        "Then log out and log in again.")
        else:
            message += "Please start Docker Desktop and try again."
        sys.exit(message)


def get_server_url() -> str:
    """
    Get the address that the nodes use to reach the server.

    Docker Desktop (Windows, macOS and some Linux computers) knows the name
    'host.docker.internal'. Docker Engine on Linux does not, so there the
    address of the Docker bridge network is used.
    """
    if platform.system() != "Linux":
        return "http://host.docker.internal"
    context = subprocess.run(["docker", "context", "show"], capture_output=True, text=True)
    if "desktop" in context.stdout:
        return "http://host.docker.internal"
    return "http://172.17.0.1"


def check_number_of_records(csv_file: Path) -> None:
    """Warn when a CSV file is too small to give every node enough records."""
    with open(csv_file) as file:
        number_of_records = sum(1 for _ in file) - 1
    records_per_node = number_of_records // NUMBER_OF_NODES
    if records_per_node < MINIMUM_RECORDS_PER_NODE:
        print(f"Warning: '{csv_file.name}' gives each node only {records_per_node} records "
              f"(at least {MINIMUM_RECORDS_PER_NODE} are advised).")


def remove_locked_node_logs() -> None:
    """
    Remove node log files that you are not allowed to change.

    On Linux, the node containers run as the administrator (root) and write their log files into
    your home folder. After that, the 'v6' command cannot open these files any more and stops
    with a 'permissions error'. The folder belongs to you, so you are allowed to delete the files;
    no administrator rights are needed. You can still read the node logs with 'docker logs'.
    """
    from vantage6.cli.context.node import NodeContext
    for number in range(1, NUMBER_OF_NODES + 1):
        log_folder = NodeContext.instance_folders("node", f"{NETWORK_NAME}_node_{number}", False)["log"]
        for log_file in Path(log_folder).glob("*.log*"):
            if not os.access(log_file, os.W_OK):
                log_file.unlink()


def shuffle_hospitals(csv_file: Path, output_folder: Path) -> Path:
    """
    Write a copy of a CSV file with its hospitals in a random order.

    'v6 dev create-demo-network' gives the first part of the rows to node 1, the second part to
    node 2, and so on. The file contains one block of rows per hospital, so changing the order of
    the blocks gives each hospital to a random node. The rows inside a block do not change.

    Returns:
        The path of the copy; it has the same name as the original file
    """
    header, *rows = csv_file.read_text().splitlines()
    number_of_rows = len(rows)
    blocks = [rows[i * number_of_rows // NUMBER_OF_NODES:(i + 1) * number_of_rows // NUMBER_OF_NODES]
              for i in range(NUMBER_OF_NODES)]
    random.shuffle(blocks)

    shuffled_file = output_folder / csv_file.name
    shuffled_file.write_text("\n".join([header] + [row for block in blocks for row in block]) + "\n")
    return shuffled_file


def network_exists() -> bool:
    """Check whether the developer network has already been created."""
    from vantage6.cli.context.server import ServerContext
    return ServerContext.config_exists(NETWORK_NAME, system_folders=False)


def create() -> None:
    """
    Create the developer network, and remove it again when this does not finish.

    'v6 dev create-demo-network' first writes the configuration files and after that fills the
    server with the users, organisations and nodes. When it stops in between, the next 'start'
    finds the configuration files, skips creating the network and starts a server without users,
    so logging in fails. Removing the half-created network makes the next 'start' begin again.
    """
    arguments = ["dev", "create-demo-network",
                 "--name", NETWORK_NAME,
                 "--num-nodes", str(NUMBER_OF_NODES),
                 "--server-port", str(SERVER_PORT),
                 "--server-url", get_server_url(),
                 "--image", IMAGES["server"],
                 "--ui-image", IMAGES["ui"]]
    try:
        with tempfile.TemporaryDirectory() as shuffled_folder:
            # Add any CSV files from the synthetic data folder; every file is split over the nodes,
            # with the hospitals in a random order
            for csv_file in sorted(SYNTHETIC_DATA_FOLDER.glob("*.csv")):
                check_number_of_records(csv_file)
                shuffled_file = shuffle_hospitals(csv_file, Path(shuffled_folder))
                arguments += ["--add-dataset", csv_file.stem, str(shuffled_file)]
            run_v6(arguments)
    except (SystemExit, KeyboardInterrupt):
        if network_exists():
            print("\nCreating the network did not finish; removing the parts that were created.")
            remove()
        raise


def start() -> None:
    check_docker()
    remove_locked_node_logs()
    if not network_exists():
        create()
    run_v6(["dev", "start-demo-network", "--name", NETWORK_NAME,
            "--server-image", IMAGES["server"],
            "--node-image", IMAGES["node"],
            "--store-image", IMAGES["algorithm-store"]])
    print("\nThe developer network is running.")
    print(f"Server: http://localhost:{SERVER_PORT}/api")
    print("Web interface: http://localhost:7600 (username: dev_admin, password: password)")
    print("You can now open the notebook.")


def stop() -> None:
    check_docker()
    remove_locked_node_logs()
    run_v6(["dev", "stop-demo-network", "--name", NETWORK_NAME])


def remove() -> None:
    check_docker()
    if not network_exists():
        print("There is no developer network to remove.")
        return
    remove_locked_node_logs()
    # 'v6 dev remove-demo-network' does nothing while the server is running, so stop it first
    run_v6(["dev", "stop-demo-network", "--name", NETWORK_NAME])
    run_v6(["dev", "remove-demo-network", "--name", NETWORK_NAME])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage the vantage6 developer network.")
    parser.add_argument("action", choices=["start", "stop", "remove"],
                        help="start, stop or remove the developer network")
    actions = {"start": start, "stop": stop, "remove": remove}
    actions[parser.parse_args().action]()
