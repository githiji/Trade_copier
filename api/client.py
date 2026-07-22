import json
import os


import requests
from .config import get_server_url, get_token

base_url = get_server_url()

def login(username, password):
    return requests.post(
        f"{base_url}/api/login/",
        json={
            "username": username,
            "password": password,
        },
        timeout=10,
    )


CONFIG_FILE = "config.json"
def send_events(events):

    if not events:
        return None

    token = get_token()

    try:
        response = requests.post(
            f"{get_server_url()}/api/events/batch/",
            json=events,
            headers={
                "Authorization": f"Token {token}"
            },
            timeout=20
        )

        response.raise_for_status()

        return response

    except requests.exceptions.Timeout:
        print("Server timeout while syncing events")
        return None

    except requests.exceptions.ConnectionError:
        print("Cannot connect to server")
        return None

    except requests.exceptions.HTTPError as e:
        print(f"API error: {e}")
        return None

def save_token(token):
    config = {}

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)

    config["token"] = token

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


    







def get_token():

    if not os.path.exists(CONFIG_FILE):
        return None

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    return config.get("token")