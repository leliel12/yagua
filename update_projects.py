#!/usr/bin/env python3
"""
Script to clone or update Git projects.
"""
import os
import subprocess
from pathlib import Path

# List of projects to clone/update
# Format: (folder_name, repository_url)
PROJECTS = [
    ("astroalign", "https://github.com/quatrope/astroalign.git"),
    # Add more projects here
    # ("project_name", "repository_url"),
]


def run_command(command, cwd=None):
    """Executes a command and returns the result."""
    try:
        result = subprocess.run(
            command, cwd=cwd, check=True, capture_output=True, text=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def clone_or_update_project(project_name, repo_url):
    """Clones a project if it doesn't exist, or pulls if it already exists."""
    project_path = Path(project_name)

    if project_path.exists():
        print(f"📁 Project '{project_name}' already exists. Updating...")

        # Verify it's a valid git repository
        if not (project_path / ".git").exists():
            print(f"⚠️  '{project_name}' exists but is not a git repository")
            return False

        # Pull changes
        success, output = run_command(["git", "pull"], cwd=project_path)

        if success:
            print(f"✅ '{project_name}' updated successfully")
            if output.strip():
                print(f"   {output.strip()}")
        else:
            print(f"❌ Error updating '{project_name}':")
            print(f"   {output}")
            return False
    else:
        print(f"📥 Cloning '{project_name}' from {repo_url}...")

        success, output = run_command(["git", "clone", repo_url, project_name])

        if success:
            print(f"✅ '{project_name}' cloned successfully")
        else:
            print(f"❌ Error cloning '{project_name}':")
            print(f"   {output}")
            return False

    return True


def main():
    """Main function."""
    print("🚀 Starting project update...\n")

    success_count = 0
    fail_count = 0

    for project_name, repo_url in PROJECTS:
        print(f"\n{'='*60}")
        if clone_or_update_project(project_name, repo_url):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"\n📊 Summary:")
    print(f"   ✅ Successful: {success_count}")
    print(f"   ❌ Failed: {fail_count}")
    print(f"   📦 Total: {len(PROJECTS)}")


if __name__ == "__main__":
    main()
