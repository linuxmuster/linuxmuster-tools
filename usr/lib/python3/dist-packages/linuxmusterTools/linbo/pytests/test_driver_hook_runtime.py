import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from linuxmusterTools.linbo.driver_hooks import render_driverpostsync


CANONICAL_TASK = (
    "LINBO-Driver-Install",
    "ProgramData/LINBO/Drivers/startup-task-ready",
    "LINBO SYSTEM driver startup task v1",
)
LEGACY_TASK = (
    "LINBO-Patchless-Driver-Install",
    "ProgramData/LINBO-Patchless/startup-task-ready",
    "LINBO-Patchless SYSTEM startup task v1",
)


@dataclass(frozen=True)
class HookRuntimeResult:
    completed: subprocess.CompletedProcess[str]
    log: str
    registry: str
    rsync_calls: list[str]
    windows_root: Path


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_generated_hook(
    tmp_path: Path,
    *,
    profile_matches: dict[str, str],
    task_contract: tuple[str, str, str],
    fail_batch_publish: bool = False,
) -> HookRuntimeResult:
    runtime = tmp_path / "runtime"
    mock_bin = runtime / "bin"
    mock_server = runtime / "server-drivers"
    runtime_tmp = runtime / "tmp"
    cache_root = runtime / "cache"
    windows_root = runtime / "mnt"
    dmi_root = runtime / "dmi"
    for directory in (
        mock_bin,
        mock_server,
        runtime_tmp,
        cache_root,
        windows_root / "Windows/System32/config",
        dmi_root,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    for profile, match_conf in profile_matches.items():
        source = mock_server / profile
        source.mkdir()
        (source / "match.conf").write_text(match_conf, encoding="utf-8")
        (source / f"{profile}.inf").write_text(
            f"fixture driver for {profile}\n", encoding="utf-8"
        )

    task_name, marker_relative, marker_value = task_contract
    task = windows_root / "Windows/System32/Tasks" / task_name
    task.parent.mkdir(parents=True)
    task.write_text("scheduled task fixture\n", encoding="utf-8")
    marker = windows_root / marker_relative
    marker.parent.mkdir(parents=True)
    marker.write_text(marker_value, encoding="utf-8")

    vendor = dmi_root / "sys_vendor"
    product = dmi_root / "product_name"
    vendor.write_text("Fixture Systems\n", encoding="utf-8")
    product.write_text("SchoolBook 14 Gen 3\n", encoding="utf-8")

    rsync_calls = runtime / "rsync-calls"
    registry_capture = runtime / "registry-capture.reg"
    _write_executable(
        mock_bin / "rsync",
        """#!/bin/sh
set -eu
while [ "$#" -gt 0 ]; do
    case "$1" in
        -*) shift ;;
        *) break ;;
    esac
done
[ "$#" -eq 2 ] || exit 64
SOURCE=$1
DESTINATION=$2
REMOTE=${SOURCE#*::linbo/drivers/}
[ "$REMOTE" != "$SOURCE" ] || exit 65
case "$REMOTE" in
    */match.conf)
        PROFILE=${REMOTE%/match.conf}
        printf 'metadata:%s\n' "$PROFILE" >> "$MOCK_RSYNC_CALLS"
        cp "$MOCK_DRIVER_SERVER/$PROFILE/match.conf" "$DESTINATION"
        ;;
    */)
        PROFILE=${REMOTE%/}
        printf 'payload:%s\n' "$PROFILE" >> "$MOCK_RSYNC_CALLS"
        mkdir -p "$DESTINATION"
        cp -R "$MOCK_DRIVER_SERVER/$PROFILE/." "$DESTINATION/"
        ;;
    *) exit 66 ;;
esac
""",
    )
    _write_executable(
        mock_bin / "linbo_patch_registry",
        """#!/bin/sh
set -eu
cp "$1" "$MOCK_REGISTRY_CAPTURE"
printf 'mock registry import completed\n'
""",
    )
    if fail_batch_publish:
        _write_executable(
            mock_bin / "mv",
            """#!/bin/sh
set -eu
for argument in "$@"; do
    destination=$argument
done
case "$destination" in
    */Drivers/LINBO/pnputil-install.cmd) exit 73 ;;
esac
exec /usr/bin/mv "$@"
""",
        )

    rendered = render_driverpostsync("win11-runtime", profile_matches)
    isolated = rendered.replace("/tmp", runtime_tmp.as_posix())
    isolated = isolated.replace("/cache", cache_root.as_posix())
    isolated = isolated.replace("/mnt", windows_root.as_posix())
    isolated = isolated.replace(
        "/sys/class/dmi/id/sys_vendor", vendor.as_posix()
    )
    isolated = isolated.replace(
        "/sys/class/dmi/id/product_name", product.as_posix()
    )
    hook = runtime / "win11-runtime.driverpostsync"
    _write_executable(hook, isolated)

    environment = os.environ.copy()
    environment.update(
        {
            "LINBOSERVER": "fixture-server",
            "MOCK_DRIVER_SERVER": str(mock_server),
            "MOCK_REGISTRY_CAPTURE": str(registry_capture),
            "MOCK_RSYNC_CALLS": str(rsync_calls),
            "PATH": f"{mock_bin}:{environment['PATH']}",
        }
    )
    completed = subprocess.run(
        ["/bin/sh", "-c", '. "$1"', "driverpostsync-runtime", str(hook)],
        cwd=runtime,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    return HookRuntimeResult(
        completed=completed,
        log=(runtime_tmp / "linbo-driverpostsync.log").read_text(encoding="utf-8"),
        registry=registry_capture.read_text(encoding="utf-8"),
        rsync_calls=rsync_calls.read_text(encoding="utf-8").splitlines(),
        windows_root=windows_root,
    )


@pytest.mark.parametrize(
    "task_contract",
    [
        pytest.param(CANONICAL_TASK, id="canonical-task-marker"),
        pytest.param(LEGACY_TASK, id="legacy-task-marker"),
    ],
)
def test_generated_hook_runs_with_system_task_and_selects_matching_profile(
    tmp_path: Path,
    task_contract: tuple[str, str, str],
) -> None:
    result = _run_generated_hook(
        tmp_path,
        profile_matches={
            "ExactModel": (
                "[match]\n"
                "vendor = Fixture Systems\n"
                "product = SchoolBook 14\n"
            ),
            "OtherVendor": (
                "[match]\n"
                "vendor = Different Systems\n"
                "product = *\n"
            ),
        },
        task_contract=task_contract,
    )

    assert result.completed.returncode == 0, result.completed.stderr
    assert result.rsync_calls == [
        "metadata:ExactModel",
        "metadata:OtherVendor",
        "payload:ExactModel",
    ]
    assert "Matched folders:  ExactModel" in result.log
    assert "SYSTEM startup task detected" in result.log
    assert "persistent SYSTEM startup task ready" in result.log
    assert '"!LinboDriverInstall"=-' in result.registry
    assert "cmd.exe /d /s /c" not in result.registry
    assert (
        result.windows_root / "Drivers/LINBO/ExactModel/ExactModel.inf"
    ).is_file()
    assert not (result.windows_root / "Drivers/LINBO/OtherVendor").exists()
    batch = result.windows_root / "Drivers/LINBO/pnputil-install.cmd"
    batch_content = batch.read_bytes()
    assert batch_content.startswith(b"@echo off\r\n")
    assert batch_content.endswith(b"exit /b 0\r\n")
    assert b"\n" not in batch_content.replace(b"\r\n", b"")
    assert not list(batch.parent.glob(".pnputil-install.cmd.tmp.*"))


def test_generated_hook_rejects_malformed_match_conf_but_keeps_valid_match(
    tmp_path: Path,
) -> None:
    result = _run_generated_hook(
        tmp_path,
        profile_matches={
            "Malformed": (
                "[match]\n"
                "vendor = Fixture Systems\n"
            ),
            "ValidModel": (
                "[match]\n"
                "vendor = Fixture Systems\n"
                "product = SchoolBook 14\n"
            ),
        },
        task_contract=CANONICAL_TASK,
    )

    assert result.completed.returncode == 1
    assert result.rsync_calls == [
        "metadata:Malformed",
        "metadata:ValidModel",
        "payload:ValidModel",
    ]
    assert "Malformed: invalid match.conf" in result.log
    assert "Matched folders:  ValidModel" in result.log
    assert not (result.windows_root / "Drivers/LINBO/Malformed").exists()
    assert (
        result.windows_root / "Drivers/LINBO/ValidModel/ValidModel.inf"
    ).is_file()


def test_generated_hook_never_publishes_a_partial_batch(
    tmp_path: Path,
) -> None:
    result = _run_generated_hook(
        tmp_path,
        profile_matches={
            "ExactModel": (
                "[match]\n"
                "vendor = Fixture Systems\n"
                "product = SchoolBook 14\n"
            ),
        },
        task_contract=CANONICAL_TASK,
        fail_batch_publish=True,
    )

    assert result.completed.returncode == 1
    assert "Failed to create pnputil-install.cmd" in result.log
    target = result.windows_root / "Drivers/LINBO"
    assert not (target / "pnputil-install.cmd").exists()
    assert not list(target.glob(".pnputil-install.cmd.tmp.*"))
    assert '"!LinboDriverInstall"=-' in result.registry
    assert "cmd.exe /d /s /c" not in result.registry
