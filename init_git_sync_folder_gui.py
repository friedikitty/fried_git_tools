#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from shlex import quote
from dataclasses import dataclass
from typing import Optional


@dataclass
class Args:
    """Arguments for git sync folder initialization."""

    repo_path: str
    remote_url: str
    remote_name: str = "origin"
    branches: list[str] = None
    no_fetch: bool = False
    verify_only: bool = False
    destination_remote_url: Optional[str] = None
    destination_remote_name: str = "destination"

    def __post_init__(self):
        """Set default for branches if None."""
        if self.branches is None:
            self.branches = ["master"]


class GUICallback:
    """UI callback class for handling user interactions in GUI mode."""

    def __init__(self, root):
        self.root = root

    def info(self, message):
        """Display info message."""
        # In GUI mode, info messages are printed to console
        # Only show messagebox for very important single-line messages
        print(message)

    def warning(self, message):
        """Display warning message."""
        # Clean up the message
        msg = message.strip().replace("[WARNING]", "").strip()
        messagebox.showwarning("Warning", msg)
        print(message)

    def error(self, message):
        """Display error message."""
        # Clean up the message
        msg = message.strip().replace("[ERROR]", "").replace("[FAILED]", "").strip()
        messagebox.showerror("Error", msg)
        print(message)

    def success(self, message):
        """Display success message."""
        # Extract the main success message
        lines = message.strip().split("\n")
        main_msg = ""
        for line in lines:
            if "[SUCEEEDED]" in line or "complete" in line.lower():
                main_msg = line.replace("[SUCEEEDED]", "").strip()
                break
        if not main_msg and lines:
            main_msg = lines[0].strip()

        # Show messagebox for important success messages
        if main_msg and (
            "complete" in main_msg.lower()
            or "initialized" in main_msg.lower()
            or "added" in main_msg.lower()
            or "updated" in main_msg.lower()
        ):
            messagebox.showinfo("Success", main_msg)
        print(message)

    def ask_yesno(self, question):
        """Ask yes/no question and return True/False."""
        response = messagebox.askyesno("Confirmation", question)
        return response


def build_command_string(args):
    """Build a command-line string that represents how init_git_sync_folder.py would be called."""
    # Get the path to init_git_sync_folder.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "init_git_sync_folder.py")

    # Use python executable if available, otherwise just the script
    if sys.executable:
        cmd_parts = [sys.executable, script_path]
    else:
        cmd_parts = ["python", script_path]

    # Add required arguments
    cmd_parts.append(f"--repo-path {quote(str(args.repo_path))}")
    cmd_parts.append(f"--remote-url {quote(str(args.remote_url))}")

    # Add optional arguments if they differ from defaults
    if args.remote_name != "origin":
        cmd_parts.append(f"--remote-name {quote(str(args.remote_name))}")

    if args.branches != ["master"]:
        # Branches is a list, join them with spaces
        branches_str = " ".join(quote(str(b)) for b in args.branches)
        cmd_parts.append(f"--branches {branches_str}")

    # Boolean flags
    if args.no_fetch:
        cmd_parts.append("--no-fetch")

    if args.verify_only:
        cmd_parts.append("--verify-only")

    # Destination remote arguments
    if args.destination_remote_url:
        cmd_parts.append(
            f"--destination-remote-url {quote(str(args.destination_remote_url))}"
        )
        if args.destination_remote_name != "destination":
            cmd_parts.append(
                f"--destination-remote-name {quote(str(args.destination_remote_name))}"
            )

    return " ".join(cmd_parts)


class GitSyncGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Git Bare Repository Initialization")
        self.root.geometry("700x600")

        # Create main frame with padding
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights for resizing
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Git Bare Repository Initialization",
            font=("Arial", 14, "bold"),
        )
        title_label.grid(row=row, column=0, columnspan=2, pady=(0, 20))
        row += 1

        # Repository Path (required)
        ttk.Label(main_frame, text="Repository Path *:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.repo_path_var = tk.StringVar()
        repo_path_entry = ttk.Entry(
            main_frame, textvariable=self.repo_path_var, width=50
        )
        repo_path_entry.grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0)
        )
        ttk.Button(main_frame, text="Browse", command=self.browse_repo_path).grid(
            row=row, column=2, padx=(5, 0), pady=5
        )
        row += 1

        # Remote URL (required)
        ttk.Label(main_frame, text="Remote URL *:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.remote_url_var = tk.StringVar()
        remote_url_entry = ttk.Entry(
            main_frame, textvariable=self.remote_url_var, width=50
        )
        remote_url_entry.grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0)
        )
        row += 1

        # Remote Name
        ttk.Label(main_frame, text="Remote Name:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.remote_name_var = tk.StringVar(value="origin")
        remote_name_entry = ttk.Entry(
            main_frame, textvariable=self.remote_name_var, width=50
        )
        remote_name_entry.grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0)
        )
        row += 1

        # Branches
        ttk.Label(main_frame, text="Branches:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.branches_var = tk.StringVar(value="master")
        branches_entry = ttk.Entry(main_frame, textvariable=self.branches_var, width=50)
        branches_entry.grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0)
        )
        ttk.Label(main_frame, text="(space-separated)", font=("Arial", 8)).grid(
            row=row, column=2, sticky=tk.W, padx=(5, 0), pady=5
        )
        row += 1

        # Checkboxes frame
        checkbox_frame = ttk.Frame(main_frame)
        checkbox_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=10)
        row += 1

        self.no_fetch_var = tk.BooleanVar()
        ttk.Checkbutton(
            checkbox_frame,
            text="Skip initial fetch (--no-fetch)",
            variable=self.no_fetch_var,
        ).grid(row=0, column=0, sticky=tk.W, padx=10)

        self.verify_only_var = tk.BooleanVar()
        ttk.Checkbutton(
            checkbox_frame,
            text="Verify only (--verify-only)",
            variable=self.verify_only_var,
        ).grid(row=0, column=1, sticky=tk.W, padx=10)

        # Separator
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=20
        )
        row += 1

        # Destination Remote Section
        dest_label = ttk.Label(
            main_frame, text="Destination Remote (Optional)", font=("Arial", 10, "bold")
        )
        dest_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        row += 1

        # Destination Remote URL
        ttk.Label(main_frame, text="Destination Remote URL:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.dest_remote_url_var = tk.StringVar()
        dest_remote_url_entry = ttk.Entry(
            main_frame, textvariable=self.dest_remote_url_var, width=50
        )
        dest_remote_url_entry.grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0)
        )
        row += 1

        # Destination Remote Name
        ttk.Label(main_frame, text="Destination Remote Name:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.dest_remote_name_var = tk.StringVar(value="destination")
        dest_remote_name_entry = ttk.Entry(
            main_frame, textvariable=self.dest_remote_name_var, width=50
        )
        dest_remote_name_entry.grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0)
        )
        row += 1

        # Command preview section
        ttk.Label(main_frame, text="Command Preview:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(20, 5)
        )
        row += 1

        self.cmd_preview = scrolledtext.ScrolledText(
            main_frame, height=6, width=70, wrap=tk.WORD
        )
        self.cmd_preview.grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # Update command preview when fields change
        for var in [
            self.repo_path_var,
            self.remote_url_var,
            self.remote_name_var,
            self.branches_var,
            self.no_fetch_var,
            self.verify_only_var,
            self.dest_remote_url_var,
            self.dest_remote_name_var,
        ]:
            var.trace_add("write", lambda *args: self.update_command_preview())

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=20)

        ttk.Button(button_frame, text="Run", command=self.run_command, width=15).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            button_frame, text="Cancel", command=self.root.destroy, width=15
        ).pack(side=tk.LEFT, padx=5)

        # Initial command preview update
        self.update_command_preview()

    def browse_repo_path(self):
        """Open a directory browser for repository path."""
        from tkinter import filedialog

        directory = filedialog.askdirectory(title="Select Repository Directory")
        if directory:
            self.repo_path_var.set(directory)

    def update_command_preview(self):
        """Update the command preview text."""
        try:
            branches_str = self.branches_var.get().strip()
            branches = branches_str.split() if branches_str else ["master"]

            args = Args(
                repo_path=self.repo_path_var.get(),
                remote_url=self.remote_url_var.get(),
                remote_name=self.remote_name_var.get() or "origin",
                branches=branches,
                no_fetch=self.no_fetch_var.get(),
                verify_only=self.verify_only_var.get(),
                destination_remote_url=self.dest_remote_url_var.get().strip() or None,
                destination_remote_name=self.dest_remote_name_var.get()
                or "destination",
            )

            cmd_string = build_command_string(args)

            self.cmd_preview.delete(1.0, tk.END)
            self.cmd_preview.insert(1.0, cmd_string)
        except Exception as e:
            self.cmd_preview.delete(1.0, tk.END)
            self.cmd_preview.insert(1.0, f"Error generating preview: {str(e)}")

    def validate_inputs(self):
        """Validate required inputs."""
        if not self.repo_path_var.get().strip():
            messagebox.showerror("Validation Error", "Repository Path is required!")
            return False

        if not self.remote_url_var.get().strip():
            messagebox.showerror("Validation Error", "Remote URL is required!")
            return False

        return True

    def run_command(self):
        """Execute the command with collected arguments."""
        if not self.validate_inputs():
            return

        branches_str = self.branches_var.get().strip()
        branches = branches_str.split() if branches_str else ["master"]

        args = Args(
            repo_path=self.repo_path_var.get().strip(),
            remote_url=self.remote_url_var.get().strip(),
            remote_name=self.remote_name_var.get().strip() or "origin",
            branches=branches,
            no_fetch=self.no_fetch_var.get(),
            verify_only=self.verify_only_var.get(),
            destination_remote_url=self.dest_remote_url_var.get().strip() or None,
            destination_remote_name=self.dest_remote_name_var.get().strip()
            or "destination",
        )

        # Print the simulated command-line call
        cmd_string = build_command_string(args)
        print("\n" + "=" * 80)
        print("Simulated Command-Line Call:")
        print("=" * 80)
        print(cmd_string)
        print("=" * 80 + "\n")

        # Import and run main_core
        from init_git_sync_folder import main_core

        # Create GUI callback for user interactions
        ui_callback = GUICallback(self.root)

        try:
            result = main_core(args, ui_callback=ui_callback)
            if result == 0:
                # Success message already shown by callback
                pass
            else:
                messagebox.showerror(
                    "Error", f"Repository initialization failed with exit code {result}"
                )
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")


def main():
    root = tk.Tk()
    app = GitSyncGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
