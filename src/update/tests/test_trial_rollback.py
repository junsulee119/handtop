"""Exercise the worker's rollback trial with dpkg metadata and no package changes."""
from importlib import machinery, util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def worker(monkeypatch):
    path = Path(__file__).resolve().parents[3] / "overlay/usr/local/sbin/handtop-update"
    loader = machinery.SourceFileLoader("handtop_update_worker", str(path))
    module = util.module_from_spec(util.spec_from_loader(loader.name, loader))
    if sys.platform == "win32":
        # The trial reads metadata and never takes the Linux file lock.
        monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace())
    loader.exec_module(module)
    monkeypatch.setattr(module, "native_arch", lambda: "arm64")

    def compare(a, op, b):
        assert op == ">="
        return int(a) >= int(b)

    monkeypatch.setattr(module, "_vcmp", compare)
    return module


def installed(name, version, *, depends="", provides="", status="ii "):
    return f"{name}\t{version}\t{depends}\t{provides}\t\t{status}"


@pytest.fixture
def trial(worker, monkeypatch):
    def check(rows, kept, *, restore=None, remove=(), forward=None):
        live = forward is None
        where = worker.PREVIOUS if live else worker.NEXT
        archives = {}

        def entries(directory, packages):
            result = []
            for name, (version, fields) in packages.items():
                file = f"{name}_{version}.deb"
                archives[Path(directory) / file] = dict(Package=name, Version=version, **fields)
                result.append(dict(name=name, version=version, file=file))
            return result

        def run(cmd, **kwargs):
            if cmd[0] == "dpkg-query":
                return SimpleNamespace(stdout="\n".join(rows))
            assert cmd[:2] == ["dpkg-deb", "-f"], cmd
            fields = archives[Path(cmd[2])]
            if len(cmd) == 4:
                return SimpleNamespace(stdout=fields.get(cmd[3], ""))
            return SimpleNamespace(stdout="\n".join(f"{f}: {fields[f]}" for f in cmd[3:] if f in fields))

        kept_entries = entries(where, kept)
        manifest = {"complete": True, "packages": kept_entries}
        if live:
            plan = {"packages": [p for p in kept_entries if restore is None or p["name"] in restore],
                    "remove": list(remove)}
        else:
            plan = {"packages": entries(worker.CACHE, forward)}
        monkeypatch.setattr(worker, "run", run)
        return worker.trial_rollback(plan, manifest, where, live=live)

    return check


@pytest.mark.parametrize(("helper_version", "fallback"), [("1", True), ("1", False), ("2", True)])
def test_live_accepts_a_healthy_alternative(trial, helper_version, fallback):
    rows = [installed("handtop-app", "2"), installed("handtop-helper", helper_version, status="hi ")]
    if fallback:
        rows.append(installed("fallback", "1"))
    kept = {"handtop-app": ("1", {"Pre-Depends": "handtop-helper | fallback"}),
            "handtop-helper": ("1", {})}
    restore = ("handtop-app",) if helper_version == "1" else ("handtop-app", "handtop-helper")
    assert trial(rows, kept, restore=restore) is None


def test_live_skips_pre_depends_of_an_archive_it_does_not_unpack(trial):
    rows = [installed("handtop-app", "2"), installed("handtop-helper", "1", depends="handtop-app")]
    kept = {"handtop-app": ("1", {}), "handtop-helper": ("1", {"Pre-Depends": "handtop-app"})}
    assert trial(rows, kept, restore=("handtop-app",)) is None


@pytest.mark.parametrize("live", [False, True])
def test_trial_refuses_when_rollback_removes_the_only_provider(trial, live):
    rows = [installed("handtop-app", "2"), installed("client", "1", depends="rollback-api"),
            installed("handtop-added", "1", provides="rollback-api")]
    reason = trial(rows, {"handtop-app": ("1", {})}, remove=("handtop-added",), forward=None if live else {})
    assert reason == "after going back, client would need rollback-api"


def test_live_checks_saved_removal_even_if_a_cut_already_removed_it(trial):
    rows = [installed("handtop-app", "2"), installed("client", "1", depends="handtop-added")]
    reason = trial(rows, {"handtop-app": ("1", {})}, remove=("handtop-added",))
    assert reason == "after going back, client would need handtop-added"


def test_depends_can_use_a_provider_installed_by_rollback(trial):
    rows = [installed("handtop-app", "2"), installed("client", "1", depends="handtop-added | rollback-api"),
            installed("handtop-added", "1")]
    kept = {"handtop-app": ("1", {"Provides": "rollback-api"})}
    assert trial(rows, kept, remove=("handtop-added",)) is None


@pytest.mark.parametrize(("provides", "status", "error"), [
    ("rollback-api (= 2)", "hi ", None),
    ("rollback-api", "ii ", "after going back"),
    ("rollback-api (= 1)", "ii ", "after going back"),
    ("rollback-api (= 2)", "iH ", "handtop-app"),
    ("rollback-api (= 2)", "iiR", "handtop-app"),
])
def test_versioned_virtual_pre_depends(trial, provides, status, error):
    rows = [installed("handtop-app", "2"), installed("provider", "9", provides=provides, status=status),
            installed("handtop-added", "1", provides="rollback-api (= 2)")]
    kept = {"handtop-app": ("1", {"Pre-Depends": "rollback-api (>= 2)"})}
    reason = trial(rows, kept, remove=("handtop-added",))
    if error is None:
        assert reason is None
    else:
        assert reason is not None and reason.startswith(error)


def test_live_refuses_a_virtual_pre_dependency_that_requires_unpack_order(trial):
    # The first archive drops the old provider and the last restores it, after the app needs it.
    rows = [installed("handtop-first", "2", provides="rollback-api (= 2)"),
            installed("handtop-app", "2"), installed("handtop-last", "2")]
    kept = {"handtop-first": ("1", {}), "handtop-app": ("1", {"Pre-Depends": "rollback-api (>= 2)"}),
            "handtop-last": ("1", {"Provides": "rollback-api (= 2)"})}
    reason = trial(rows, kept)
    assert reason is not None and reason.startswith("handtop-app") and "rollback-api" in reason


def test_live_counts_a_reinstall_still_in_the_saved_plan_on_retry(trial):
    rows = [installed("handtop-app", "2"), installed("handtop-helper", "1")]
    kept = {"handtop-app": ("1", {"Pre-Depends": "handtop-helper"}), "handtop-helper": ("1", {})}
    reason = trial(rows, kept)
    assert reason is not None and "handtop-helper" in reason


@pytest.mark.parametrize(("status", "forward", "affected"), [
    ("hi ", {}, None),
    ("iU ", {}, "old-api"),
    ("iU ", {"handtop-helper": ("1", {"Provides": "old-api"})}, None),
    ("ii ", {"handtop-helper": ("2", {"Provides": "new-api"})}, "new-api, old-api"),
])
def test_download_derives_touched_provides_from_the_projected_state(trial, status, forward, affected):
    rows = [installed("handtop-helper", "1", provides="old-api", status=status),
            installed("client:amd64", "1", depends="old-api | new-api")]
    kept = {"handtop-helper": ("1", {"Provides": "old-api"})}
    reason = trial(rows, kept, forward=forward)
    assert reason == (f"client:amd64 (another architecture) depends on {affected}" if affected else None)


def test_live_still_refuses_foreign_packages(trial):
    rows = [installed("handtop-app", "2"), installed("client:amd64", "1")]
    assert trial(rows, {"handtop-app": ("1", {})}) == "packages for another architecture are installed (client:amd64)"


def test_install_recovery_passes_the_saved_plan_to_the_trial(worker, monkeypatch):
    plan = {"packages": [], "remove": ["handtop-added"]}
    manifest = {"complete": True, "packages": []}
    check = Mock(return_value="unsafe rollback")
    monkeypatch.setattr(worker, "dpkg_state_check", Mock())
    monkeypatch.setattr(worker, "read_json", Mock(return_value=manifest))
    monkeypatch.setattr(worker, "trial_rollback", check)
    with pytest.raises(worker.Drift, match="unsafe rollback"):
        worker.install_recovery(plan, None, None)
    check.assert_called_once_with(plan, manifest, worker.PREVIOUS, live=True)


def test_install_recovery_refuses_drift_in_an_omitted_kept_package(worker, monkeypatch):
    plan = {"packages": [], "remove": []}
    manifest = {"complete": True, "packages": [{"name": "handtop-helper", "version": "1"}]}
    monkeypatch.setattr(worker, "dpkg_state_check", Mock())
    monkeypatch.setattr(worker, "read_json", Mock(return_value=manifest))
    monkeypatch.setattr(worker, "plan_changed", Mock(return_value=False))
    monkeypatch.setattr(worker, "installed_any", Mock(return_value={"handtop-helper": "7"}))
    monkeypatch.setattr(worker, "installed_healthy", Mock(return_value={"handtop-helper": "7"}))
    monkeypatch.setattr(worker, "trial_rollback", Mock(return_value=None))
    with pytest.raises(worker.Drift, match="handtop-helper changed since going back was requested"):
        worker.install_recovery(plan, None, None)
