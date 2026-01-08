#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trigger a TeamCity build for each changed git branch.

Expected input (typically wired from TeamCity parameters):

    deploy_teamcity_sync_job.py --changed <true|false> --changed_json "<json>" \\
                                --teamcity_job_id <id> --teamcity_token <token> \\
                                --teamcity_url <url>

Where:
    --changed        : "true"/"false" (case-insensitive). If not true, script exits without triggering builds.
    --changed_json   : JSON string, same structure as env.git.remoteBranchesJson from check_remote_change.py, e.g.:
                     {
                       "changed": {
                         "master": {
                           "local": "28d698...",
                           "remote": "604678..."
                         }
                       },
                       "no_remote": {},
                       "unchanged": {
                         "develop": "28d698..."
                       }
                     }
    --teamcity_job_id: TeamCity build configuration ID to trigger for each changed branch.
    --teamcity_token : TeamCity Bearer token used to authenticate the REST request.
    --teamcity_url   : TeamCity server URL.

For every branch listed under the "changed" key, this script triggers a TeamCity build
for that branch, using the common TeamCity REST wrapper in custom_build/common/teamcity.
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import List

# Add the script's directory to sys.path so we can import teamcity_operate_v2 from the same directory
# _script_dir = Path(__file__).parent.absolute()
# if str(_script_dir) not in sys.path:
#     sys.path.insert(0, str(_script_dir))


def parse_bool(value: str) -> bool:
    """Parse a truthy / falsy string into a boolean."""
    if value is None:
        return False
    value = value.strip().lower()
    return value in ("1", "true", "yes", "y", "on")


def parse_args(argv: List[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Trigger TeamCity builds for each changed git branch.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --changed true \\
           --changed_json "{\"changed\": {\"master\": {\"local\": \"abc\", \"remote\": \"def\"}}, \"no_remote\": {}, \"unchanged\": {}}" \\
           --teamcity_job_id SomeBuildConfigId \\
           --teamcity_token my_teamcity_token \\
           --teamcity_url http://10.0.0.1:8080
""",
    )

    parser.add_argument(
        "--changed",
        required=True,
        help="Whether there are changed branches (true/false). "
        "If not true, no TeamCity build will be triggered.",
    )
    parser.add_argument(
        "--changed_json",
        required=True,
        dest="changed_json",
        help="JSON string describing changed / no_remote / unchanged branches, "
        "compatible with output of git_sync/check_remote_change.py.",
    )
    parser.add_argument(
        "--teamcity_job_id",
        required=True,
        dest="teamcity_job_id",
        help="TeamCity build configuration ID to trigger for each changed branch.",
    )
    parser.add_argument(
        "--teamcity_token",
        required=True,
        dest="teamcity_token",
        help="TeamCity Bearer token used for authentication.",
    )
    parser.add_argument(
        "--teamcity_url",
        required=True,
        dest="teamcity_url",
        help="TeamCity URL",
    )

    return parser.parse_args(argv)


def extract_changed_branches(changed_json: str) -> List[str]:
    """Return the list of branch names under the 'changed' key."""
    try:
        # Allow changed_json to be passed as Base64URL-encoded JSON (safe for HTTP params).
        raw = changed_json.strip()
        # Restore missing padding for Base64URL, then decode
        padding = "=" * (-len(raw) % 4)
        decoded_json = base64.urlsafe_b64decode(raw + padding).decode("utf-8")
        print("decoded_json: \n", decoded_json)
        data = json.loads(decoded_json)
    except json.JSONDecodeError as e:
        print(f"Error: failed to parse changed_json as JSON: {e}")
        sys.exit(1)

    changed = data.get("changed") or {}
    if not isinstance(changed, dict):
        print("Error: 'changed' field in JSON is not an object/dict.")
        sys.exit(1)

    return sorted(changed.keys())


def trigger_teamcity_builds(
    branches: List[str], teamcity_url: str, teamcity_job_id: str, teamcity_token: str
) -> None:
    """Trigger TeamCity builds for the given branches using the v2 TeamCity helper."""
    if not branches:
        print("No changed branches detected in JSON; nothing to trigger.")
        return

    # Import lazily so that unit tests that don't have full deps can still import this module.
    try:
        from . import teamcity_operate_v2
    except ImportError as e:
        print(
            "Error: failed to import git_sync.teamcity.teamcity_operate_v2. "
            "Ensure the repository root is on PYTHONPATH when running this script."
        )
        print(f"ImportError: {e}")
        sys.exit(1)

    overall_success = True

    for branch in branches:
        print(
            f"Triggering TeamCity job '{teamcity_job_id}' for branch '{branch}'..."
        )
        # No extra build parameters for now – extend here if needed.
        build_url, build_data = teamcity_operate_v2.build_config(
            teamcity_url, teamcity_job_id, {'branch': branch}
        )

        success, msg = teamcity_operate_v2.send(build_url, build_data, teamcity_token)
        print(msg)
        if not success:
            overall_success = False

    if not overall_success:
        sys.exit(1)


def main(argv: List[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)

    if not parse_bool(args.changed):
        print(
            f"changed={args.changed!r} evaluates to False; "
            "no TeamCity builds will be triggered."
        )
        return

    branches = extract_changed_branches(args.changed_json)
    if not branches:
        print(
            "changed is true, but no branches found under 'changed' in JSON; "
            "no TeamCity builds will be triggered."
        )
        return

    print(f"Found changed branches: {', '.join(branches)}")
    trigger_teamcity_builds(
        branches, args.teamcity_url, args.teamcity_job_id, args.teamcity_token
    )


if __name__ == "__main__":
    main()


