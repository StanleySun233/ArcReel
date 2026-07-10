from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATABASE_URL = "postgresql+asyncpg://arcreel_app:arcreel_app_dev_password@127.0.0.1:15432/arcreel"
DEFAULT_ADMIN_DATABASE_URL = "postgresql+asyncpg://arcreel:arcreel_dev_password@127.0.0.1:15432/arcreel"


@dataclass(frozen=True)
class ScenarioGroup:
    name: str
    scenario_ids: tuple[str, ...]
    tests: tuple[str, ...]


SCENARIO_GROUPS: tuple[ScenarioGroup, ...] = (
    ScenarioGroup(
        name="auth_roles",
        scenario_ids=(
            "AUTH-01",
            "AUTH-03",
            "AUTH-04",
            "AUTH-05",
            "AUTH-06",
            "AUTH-07",
            "ROLE-01",
            "ROLE-04",
            "ROLE-05",
            "ROLE-06",
            "ROLE-09",
            "CFG-06",
            "CFG-07",
        ),
        tests=(
            "tests/test_tenant_auth_service.py",
            "tests/test_tenant_auth_router.py",
            "tests/test_auth_api_key.py",
            "tests/test_api_keys_router.py",
        ),
    ),
    ScenarioGroup(
        name="rls_config",
        scenario_ids=(
            "RLS-01",
            "RLS-02",
            "RLS-03",
            "RLS-04",
            "RLS-06",
            "CFG-01",
            "CFG-02",
            "CFG-03",
            "CFG-04",
            "CFG-05",
            "CAMEL-08",
            "CAMEL-09",
        ),
        tests=(
            "tests/test_tenant_rls.py",
            "tests/test_tenant_context.py",
            "tests/test_tenant_config_isolation.py",
        ),
    ),
    ScenarioGroup(
        name="files_projects_assets",
        scenario_ids=(
            "FILE-01",
            "FILE-02",
            "FILE-04",
            "FILE-05",
            "PROJ-01",
            "PROJ-02",
            "PROJ-03",
            "PROJ-04",
            "PROJ-05",
            "PROJ-06",
            "PROJ-07",
            "ASSET-01",
            "ASSET-02",
            "ASSET-03",
            "ASSET-04",
            "ASSET-06",
            "ASSET-07",
            "ASSET-08",
            "ASSET-09",
        ),
        tests=(
            "tests/test_minio_storage.py",
            "tests/test_file_service.py",
            "tests/test_files_api_minio.py",
            "tests/test_shot_uploads_minio.py",
            "tests/test_tenant_project_registry.py",
            "tests/test_project_file_id_validation.py",
            "tests/test_tenant_project_routes.py",
            "tests/test_projects_router.py",
            "tests/test_assets_router.py",
            "tests/test_asset_repo.py",
            "tests/test_asset_model.py",
            "tests/test_asset_router_factory.py",
            "tests/test_asset_types_product.py",
        ),
    ),
    ScenarioGroup(
        name="generation_tasks_usage",
        scenario_ids=(
            "GEN-01",
            "GEN-02",
            "GEN-03",
            "GEN-04",
            "GEN-05",
            "GEN-06",
            "GEN-07",
            "GEN-08",
        ),
        tests=(
            "tests/test_generation_tasks_service.py",
            "tests/test_generation_tasks_dispatch.py",
            "tests/test_generation_queue.py",
            "tests/test_task_repo.py",
            "tests/test_tasks_router_more.py",
            "tests/test_task_cancel_router.py",
        ),
    ),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _python() -> list[str]:
    configured = os.environ.get("ARCREEL_SCENARIO_PYTHON")
    if configured:
        return configured.split()
    conda = Path("/data/data1/HOME_DIR/sijin/miniconda3/bin/conda")
    if conda.exists():
        return [str(conda), "run", "-n", "arcreel", "python"]
    return [sys.executable]


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("DATABASE_URL", DEFAULT_DATABASE_URL)
    env.setdefault("ARCREEL_TEST_DATABASE_ADMIN_URL", DEFAULT_ADMIN_DATABASE_URL)
    return env


def _selected_groups(names: list[str]) -> tuple[ScenarioGroup, ...]:
    if not names or names == ["all"]:
        return SCENARIO_GROUPS
    known = {group.name: group for group in SCENARIO_GROUPS}
    missing = [name for name in names if name not in known]
    if missing:
        raise SystemExit(f"Unknown scenario group: {', '.join(missing)}")
    return tuple(known[name] for name in names)


def _scenario_report(groups: tuple[ScenarioGroup, ...]) -> list[dict[str, object]]:
    return [
        {
            "group": group.name,
            "scenario_ids": list(group.scenario_ids),
            "tests": list(group.tests),
        }
        for group in groups
    ]


def _run_group(group: ScenarioGroup, *, extra_pytest_args: list[str]) -> int:
    cmd = [*_python(), "-m", "pytest", *group.tests, *extra_pytest_args]
    print(f"## {group.name}")
    print("scenarios:", ", ".join(group.scenario_ids))
    print("command:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=_repo_root(), env=_env(), check=False)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    groups = _selected_groups(args.group)
    if args.list:
        report = _scenario_report(groups)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            for item in report:
                print(f"{item['group']}: {', '.join(item['scenario_ids'])}")
        return 0

    extra_pytest_args = list(args.pytest_args)
    if extra_pytest_args and extra_pytest_args[0] == "--":
        extra_pytest_args = extra_pytest_args[1:]
    if not extra_pytest_args:
        extra_pytest_args = ["-q"]

    for group in groups:
        code = _run_group(group, extra_pytest_args=extra_pytest_args)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
