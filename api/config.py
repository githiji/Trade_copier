import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "server_url": "https://trade-performance-tracker-1.onrender.com",
    "token": "",
    "username": ""
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


def get_server_url():
    return load_config()["server_url"]


def set_server_url(url):
    config = load_config()
    config["server_url"] = url.rstrip("/")
    save_config(config)


def get_token():
    return load_config()["token"]


def set_token(token):
    config = load_config()
    config["token"] = token
    save_config(config)


def get_username():
    return load_config()["username"]


def set_username(username):
    config = load_config()
    config["username"] = username
    save_config(config)


def logout():
    config = load_config()
    config["token"] = ""
    config["username"] = ""
    save_config(config)