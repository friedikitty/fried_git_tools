#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lightweight TeamCity REST helpers that do not rely on a local conf module.
All required connection details (server URL, tokens, etc.) are passed in
through function parameters.
"""

import json
from typing import Dict, Tuple, Any

import requests
import xml.etree.ElementTree as ET


def build_config(
    server_url: str, build_id: str, properties: Dict[str, str]
) -> Tuple[str, Dict[str, Any]]:
    """Build the TeamCity queue URL and request body for a build.

    Args:
        server_url: Base TeamCity server URL, e.g. "http://10.0.0.1:8080".
        build_id: TeamCity build configuration ID.
        branch_name: Branch name to build.
        properties: Additional build parameters to send.

    Returns:
        (build_url, build_data) tuple ready to be used with ``send``.
    """
    server_url = server_url.rstrip("/")
    build_url = f"{server_url}/app/rest/buildQueue"
    build_data: Dict[str, Any] = {
        "buildType": {"id": build_id},
        "properties": {"property": []},
    }

    for key, value in properties.items():
        kv = {"name": key, "value": value}
        if kv not in build_data["properties"]["property"]:
            build_data["properties"]["property"].append(kv)

    # Print build_data without sensitive information
    safe_build_data = json.dumps(build_data, indent=2)
    print(safe_build_data)
    return build_url, build_data


def send(build_url: str, build_data: Dict[str, Any], token: str) -> Tuple[bool, str]:
    """Send a POST request to trigger a TeamCity build.

    Args:
        build_url: Full URL to the TeamCity build queue endpoint.
        build_data: JSON body to send.
        token: Bearer token used for authentication.

    Returns:
        (success, message) tuple describing the result.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    import six

    response = requests.post(build_url, data=json.dumps(build_data), headers=headers)
    if response.status_code == 200:
        msg = "Build started successfully."
        return True, msg
    else:
        msg = "Failed to start build: {}".format(
            six.ensure_str(response.content, "utf-8")
        )
        return False, msg


def get(build_url: str, token: str) -> requests.Response:
    """Send a GET request to the given TeamCity URL using the provided token."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    response = requests.get(build_url, headers=headers)
    return response


def put(build_url: str, body: str, token: str) -> None:
    """Send a PUT request with a plain-text body to the given TeamCity URL."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain",
    }
    resp = requests.put(build_url, data=body, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError("Failed to change TeamCity properties")


def set_vcs_root(server_url: str, token: str, vcs_id: str, new_url: str) -> None:
    """Update the VCS root URL for the given VCS root ID."""
    server_url = server_url.rstrip("/")
    build_url = f"{server_url}/app/rest/vcs-roots/id:{vcs_id}/properties/url"
    put(build_url, new_url, token)


def get_vcs_root(server_url: str, token: str, vcs_id: str) -> str:
    """Get the VCS root URL for the given VCS root ID."""
    server_url = server_url.rstrip("/")
    build_url = f"{server_url}/app/rest/vcs-roots/id:{vcs_id}/properties/url"
    r = get(build_url, token)
    return r.text


def set_teamcity_param(
    server_url: str, token: str, project_id: str, parameter_name: str, parameter_value: str
) -> None:
    """Set a TeamCity project parameter."""
    server_url = server_url.rstrip("/")
    build_url = f"{server_url}/app/rest/projects/{project_id}/parameters/{parameter_name}"
    put(build_url, parameter_value, token)


def get_teamcity_param(
    server_url: str, token: str, project_id: str, parameter_name: str
) -> str:
    """Get a TeamCity project parameter value."""
    server_url = server_url.rstrip("/")
    build_url = f"{server_url}/app/rest/projects/{project_id}/parameters/{parameter_name}"
    r = get(build_url, token)
    return r.text


def set_backup(
    server_url: str, backup_token: str, backup_url: str | None = None, filename: str | None = None
) -> None:
    """Trigger a TeamCity server backup.

    Only starts a backup when the server reports an 'Idle' state.
    """
    server_url = server_url.rstrip("/")
    if not backup_url:
        backup_url = f"{server_url}/app/rest/server/backup"
    if not filename:
        filename = "teamcity_backup.zip"

    headers = {
        "Authorization": f"Bearer {backup_token}",
        "Content-Type": "text/plain",
    }
    print(backup_url)
    r = requests.get(backup_url, headers=headers)
    print(r.text)

    # Only trigger backup when server state is Idle
    if r.text == "Idle":
        config = (
            "?includeConfigs=true&includeDatabase=true&includeBuildLogs=true"
            f"&fileName={filename}"
        )
        backup_config_url = backup_url + config
        response = requests.post(backup_config_url, headers=headers)
        if response.status_code == 200:
            print("Backup started successfully.")
        else:
            print(f"Failed to backup: {response.content}")


def download_backup(
    server_url: str, backup_token: str, backup_url: str, filename: str
) -> None:
    """Wait for backup completion and then download the backup file locally."""
    server_url = server_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {backup_token}",
        "Content-Type": "text/plain",
    }

    # Sanitize headers before printing to avoid token leak
    safe_headers = {k: "***" if k == "Authorization" else v for k, v in headers.items()}
    print("download_backup: ", backup_url, filename, safe_headers)
    r = requests.get(backup_url, headers=headers)

    while r.text != "Idle":
        r = requests.get(backup_url, headers=headers)
        print(r.text)

    # Download to local disk
    import urllib.request

    download_backup_url = f"{server_url}/downloadBackup/{filename}"
    print("download_backup_url: ", download_backup_url)

    req = urllib.request.Request(download_backup_url, headers=headers)
    response = urllib.request.urlopen(req)
    content = response.read()
    response.close()
    with open(filename, "wb") as f:
        f.write(content)


def process_args(args):
    """Convert a list of 'key=value' strings into a dictionary."""
    kwargs = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            kwargs[key] = value
    return kwargs


if __name__ == "__main__":
    print("teamcity_operate_v2 is a helper module; import and call its functions instead.")
