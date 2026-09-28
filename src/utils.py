"""
Helper functions that both course notebooks use: checking the server, listing the organisations
and sending tasks.
"""
import requests

from . import COLLABORATION_ID


def check_server(config):
    """
    Check whether the vantage6 server can be reached and print the result.

    Args:
        config: Dictionary with the server_url, server_port, and server_api
    """
    version_url = f"{config['server_url']}:{config['server_port']}{config['server_api']}/version"
    try:
        response = requests.get(version_url, timeout=10)
        response.raise_for_status()
        print(f"The server is running. Server version: {response.json().get('version')}")
    except requests.exceptions.RequestException:
        print("The server cannot be reached. "
              "Is Docker running, and did you start the network with 'python dev_network.py start'?")


def show_organisations(client, collaboration_id=COLLABORATION_ID):
    """
    Print the ID and name of every organisation in the collaboration.

    Args:
        client: An authenticated vantage6 client
        collaboration_id: The ID of the collaboration
    """
    for organisation in client.organization.list(collaboration=collaboration_id)["data"]:
        print(f"{organisation['id']}: {organisation['name']}")


def send_task(client, organisations, method, arguments, database_label, image, name):
    """
    Send a task with an algorithm to one or more organisations.

    Args:
        client: An authenticated vantage6 client
        organisations: List of IDs of the organisations that should run the task
        method: The function of the algorithm to run, e.g. 'partial_general_statistics' or 'central'
        arguments: Dictionary with the input for that function, e.g. the variables to describe
        database_label: The label of the data set on the nodes
        image: The Docker image of the algorithm
        name: A short name for the task, shown on the website of the server

    Returns:
        A dictionary with the details of the created task, including its 'id'
    """
    task = client.task.create(
        collaboration=COLLABORATION_ID,
        organizations=organisations,
        name=name,
        image=image,
        description=f"{name} (course notebook)",
        input_={"method": method, "kwargs": arguments},
        databases=[{"label": database_label}],
    )
    if "id" not in task:
        raise RuntimeError(f"The task could not be created: {task.get('msg', task)}")
    print(f"Task {task['id']} ({method}) was sent to organisation(s) {organisations}.")
    return task
