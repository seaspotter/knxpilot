"""In-app update (Update tab) against real throwaway git repos: code-only
updates are pulled, updates that change requirements.txt/Dockerfile are NOT
pulled (that would leave new code running on old packages) - the server
command is shown instead."""
import subprocess

import pytest

from backend.routers import system
from conftest import ok


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                          capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repos(tmp_path, monkeypatch):
    """upstream (bare) <- dev clone that pushes changes; server = the app's checkout."""
    upstream, dev, server = tmp_path / "upstream.git", tmp_path / "dev", tmp_path / "server"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(upstream))
    git(tmp_path, "clone", "-q", str(upstream), str(dev))
    git(dev, "checkout", "-q", "-b", "main")
    (dev / "requirements.txt").write_text("fastapi\n")
    (dev / "app.py").write_text("v1\n")
    git(dev, "add", ".")
    git(dev, "commit", "-q", "-m", "v1")
    git(dev, "push", "-q", "-u", "origin", "main")
    git(tmp_path, "clone", "-q", str(upstream), str(server))
    monkeypatch.setattr(system, "REPO_DIR", str(server))
    monkeypatch.setattr(system, "_restart_process", lambda: None)  # the real one ends the process

    def push(filename, content):
        (dev / filename).write_text(content)
        git(dev, "commit", "-q", "-am", f"change {filename}")
        git(dev, "push", "-q")
    return server, push


def test_code_only_update_is_pulled(client, repos):
    server, push = repos
    push("app.py", "v2\n")
    status = ok(client.get("/api/system/status"))
    assert status["update_available"] and not status["needs_image"]
    result = ok(client.post("/api/system/update"))
    assert result["ok"] and result["restarting"]
    assert (server / "app.py").read_text() == "v2\n"


def test_update_with_new_packages_is_not_pulled(client, repos):
    server, push = repos
    push("requirements.txt", "fastapi\njinja2\n")
    before = git(server, "rev-parse", "HEAD")
    status = ok(client.get("/api/system/status"))
    assert status["update_available"] and status["needs_image"]
    assert status["image_command"] == "git pull && docker compose pull && docker compose up -d"

    result = ok(client.post("/api/system/update"))
    assert result["needs_image"] and not result["ok"] and not result["restarting"]
    assert git(server, "rev-parse", "HEAD") == before              # nothing pulled
    assert (server / "requirements.txt").read_text() == "fastapi\n"


def test_dev_checkout_command_uses_dev_image(client, repos):
    server, push = repos
    git(server, "checkout", "-q", "-b", "dev", "--track", "origin/main")  # a checkout not on main
    push("requirements.txt", "fastapi\njinja2\n")
    status = ok(client.get("/api/system/status"))
    assert "KNXPILOT_IMAGE_TAG=dev" in status["image_command"]
    assert status["image_command"].endswith("git pull && docker compose pull && docker compose up -d")
