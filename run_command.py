# -*- coding: utf-8 -*-
"""----------------------------------------------------------------------------
Author:
    f.f.
Date:
    2021/06/07
Description:
	run command

History:
    2021/06/07, create file.
    2024/12/19, fixed naming conventions and Python 3 compatibility.
    2024/12/19, added new _run_command using modern subprocess.run approach.
----------------------------------------------------------------------------"""

import subprocess
import sys


class ConsoleCommandLogger:
    """Simple logger for command output that writes to console with clear separation."""

    def __init__(self, prefix="[CMD]"):
        """
        Initialize console logger.

        :param prefix: Prefix to use for separating command logs from main process logs
        """
        self.prefix = prefix

    def info(self, message):
        """Log info message to console."""
        print(f"{self.prefix} {message}")

    def error(self, message):
        """Log error message to console."""
        print(f"{self.prefix} ERROR: {message}")


# Inline logger class that captures output for regex error checking
# while forwarding logs to the original logger
class OutputCaptureLogger:
    def __init__(self, original_logger):
        self.original_logger = original_logger
        self.captured_output = []

    def info(self, message):
        """Capture and forward info messages."""
        self.captured_output.append(message)
        if self.original_logger:
            self.original_logger.info(message)

    def error(self, message):
        """Capture and forward error messages."""
        self.captured_output.append(message)
        if self.original_logger:
            self.original_logger.error(message)

    def get_output(self):
        """Get all captured output as a single string."""
        return "\n".join(self.captured_output)


def _run_command_deprecated(cmd, cwd=None, logger=None, shell=False, timeout=300):
    """DEPRECATED: Old command execution using subprocess.Popen - kept for manual reference.

    This function demonstrates the old approach that required manual decoding.
    Use _run_command() instead for better Python 3 compatibility.
    """
    try:
        print(f"Running: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
        if cwd:
            print(f"  Working directory: {cwd}")

        p = subprocess.Popen(
            cmd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            text=True,
            # encoding="utf-8",
            errors="replace",
            bufsize=1,  # Line buffered
            universal_newlines=True,
        )

        # Read output line by line in real-time
        while True:
            output = p.stdout.readline()
            if output == "" and p.poll() is not None:
                break
            if output:
                line = output.strip()
                if line:  # Only print non-empty lines
                    print(f"  | {line}")
                    if logger:
                        logger.info(line)

        # Wait for process completion with timeout
        try:
            return_code = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            raise Exception(f"Command timed out after {timeout} seconds")

        print(f"Command completed with return code: {return_code}")
        if logger:
            logger.info("Return: " + str(return_code))
        return return_code

    except Exception as e:
        import traceback

        err_formatted = traceback.format_exc()
        if logger:
            logger.error(err_formatted)
        print(f"Command failed: {err_formatted}")
        raise


def _run_command(
    cmd,
    cwd=None,
    logger=None,
    shell=False,
    timeout=300,
    stderr_to_stdout=False,
    error_regex=None,
):
    """Modern command execution using subprocess.run with automatic text handling.

    This is the recommended approach for Python 3 as it automatically handles
    text encoding without manual decode/encode operations.

    :param stderr_to_stdout: If True, treat stderr as stdout (merge streams)
    :param error_regex: Optional regex pattern to detect error lines (case-insensitive)
    """
    import re

    try:
        print(f"Running: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
        if cwd:
            print(f"  Working directory: {cwd}")

        # Use subprocess.run with text=True for automatic text handling
        result = subprocess.run(
            cmd,
            shell=shell,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

        # Compile error regex if provided
        error_pattern = None
        if error_regex:
            error_pattern = re.compile(error_regex, re.IGNORECASE)

        # Process stdout
        if result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():  # Only print non-empty lines
                    # Check if line matches error regex
                    is_error = error_pattern and error_pattern.search(line.strip())
                    if is_error:
                        if logger:
                            logger.error(line.strip())
                        else:
                            print(f"  | ERROR: {line.strip()}")
                    else:
                        if logger:
                            logger.info(line.strip())
                        else:
                            print(f"  | {line.strip()}")

        # Process stderr
        if result.stderr:
            for line in result.stderr.splitlines():
                if line.strip():  # Only print non-empty lines
                    if stderr_to_stdout:
                        # Treat stderr as stdout (merge streams)
                        is_error = error_pattern and error_pattern.search(line.strip())
                        if is_error:
                            if logger:
                                logger.error(line.strip())
                            else:
                                print(f"  | ERROR: {line.strip()}")
                        else:
                            if logger:
                                logger.info(line.strip())
                            else:
                                print(f"  | {line.strip()}")
                    else:
                        # Default behavior: always treat stderr as error
                        if logger:
                            logger.error(line.strip())
                        else:
                            print(f"  | ERROR: {line.strip()}")

        print(f"Command completed with return code: {result.returncode}")
        if logger:
            logger.info("Return: " + str(result.returncode))

        return result.returncode

    except subprocess.TimeoutExpired:
        error_msg = f"Command timed out after {timeout} seconds"
        print(f"ERROR: {error_msg}")
        if logger:
            logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        import traceback

        err_formatted = traceback.format_exc()
        if logger:
            logger.error(err_formatted)
        print(f"Command failed: {err_formatted}")
        raise


def run_command_and_ensure_zero(*args, **kwargs):
    """Run command and raise exception if return code is not zero."""
    ret_code = run_command(*args, **kwargs)
    if ret_code != 0:
        kwargs_string = "".join([("%s=%s" % x) for x in kwargs.items()])
        raise Exception('error command: "%s %s"' % ("".join(args), kwargs_string))


def run_command(
    cmd,
    cwd=None,
    logger=None,
    shell=False,
    timeout=300,
    stderr_to_stdout=False,
    error_regex=None,
):
    """Run a command with real-time output.

    :param cmd: See subprocess.Popen, can be a single string or a list
    :param cwd: Optional current directory
    :param logger: A python logger alike class instance to accept info or error
    :param shell: Whether to use shell
    :param timeout: Timeout in seconds
    :param stderr_to_stdout: If True, treat stderr as stdout (merge streams)
    :param error_regex: Optional regex pattern to detect error lines (case-insensitive)
    :return: Return what the command return
    """
    try:
        return _run_command(
            cmd, cwd, logger, shell, timeout, stderr_to_stdout, error_regex
        )
    except Exception as e:
        if logger:
            logger.error(f"Command execution failed: {e}")
        print(f"Command execution failed: {e}")
        return -1


def run_detached_command(command):
    """Run an external command detached, letting it run independently."""
    from subprocess import Popen

    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        cmd = ["cmd.exe", "/c"]

        if isinstance(command, str):
            cmd.append(command)
        elif isinstance(command, list):
            cmd = cmd + command
        else:
            raise Exception("Illegal command type {}".format(type(command)))

        print("run_detached_command: {}".format(cmd))
        p = Popen(
            cmd,
            shell=True,
            stdin=None,
            stdout=None,
            stderr=None,
            close_fds=True,
            creationflags=DETACHED_PROCESS,
        )
    else:
        # Unix-like systems
        if isinstance(command, str):
            cmd = command
        elif isinstance(command, list):
            cmd = " ".join(command)
        else:
            raise Exception("Illegal command type {}".format(type(command)))

        print("run_detached_command: {}".format(cmd))
        p = Popen(
            cmd,
            shell=True,
            stdin=None,
            stdout=None,
            stderr=None,
            close_fds=True,
            start_new_session=True,
        )

    print("Process: {}".format(p))
    return p


def run_command_and_get_return_info(
    command, cwd=None, shell=True, encoding="utf-8", timeout=300
):
    """Run command and return output info."""
    print("run_command_and_get_return_info: {}".format(command))
    try:
        return_info = subprocess.check_output(
            command,
            shell=shell,
            timeout=timeout,
            text=True,
            encoding=encoding,
            cwd=cwd,
            errors="replace",
        )
        return return_info
    except subprocess.CalledProcessError as e:
        print(f"Command failed with return code {e.returncode}: {e.output}")
        raise
    except subprocess.TimeoutExpired:
        print(f"Command timed out after {timeout} seconds")
        raise
