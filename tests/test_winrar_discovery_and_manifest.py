import hashlib
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive.archive_validator_repository import validate_archive_parts  # noqa: E402
from app.repository.archive.archive_hash_repository import compute_hash_streaming  # noqa: E402
from app.repository.integrity.hash_algorithm_repository import (  # noqa: E402
    normalize_manifest_hashes,
    normalize_manifest_part_hash,
)
from app.repository.archive.winrar_discovery_repository import (  # noqa: E402
    WinRarCapability,
    discover_winrar,
)
from app.services.archive.archive_manifest_service import (  # noqa: E402
    assemble_archive_manifest,
    capture_archive_file_identities,
    compute_disc_capacity,
    validate_manifest_files,
    validate_manifest_metadata,
    validate_published_manifest,
)


def probe_ok(args, **kwargs):
    return subprocess.CompletedProcess(args, 0, "WinRAR 6.24\n-v<bytes>b", "")


@pytest.mark.parametrize(
    ("algorithm", "length"), [("md5", 32), ("sha1", 40), ("sha256", 64)],
)
def test_manifest_part_hash_normalizes_all_selected_algorithms(algorithm, length):
    assert normalize_manifest_part_hash({
        "hash_algorithm": algorithm,
        "hash_value": "A" * length,
    }) == (algorithm, "a" * length)


def test_manifest_part_hash_accepts_legacy_md5_but_never_falls_back_from_new_fields():
    assert normalize_manifest_part_hash({"md5": "A" * 32}) == ("md5", "a" * 32)
    with pytest.raises(ValueError, match="ARCHIVE_BUSINESS_HASH_INVALID"):
        normalize_manifest_part_hash({
            "hash_algorithm": "sha256", "hash_value": "", "md5": "a" * 32,
        })
    with pytest.raises(ValueError, match="ARCHIVE_BUSINESS_HASH_INVALID"):
        normalize_manifest_part_hash({"hash_value": "a" * 32, "md5": "a" * 32})


def test_manifest_hashes_reject_mixed_algorithms_and_invalid_lengths():
    with pytest.raises(ValueError, match="ARCHIVE_BUSINESS_HASH_INVALID"):
        normalize_manifest_hashes([
            {"hash_algorithm": "md5", "hash_value": "a" * 32},
            {"hash_algorithm": "sha1", "hash_value": "b" * 40},
        ])
    with pytest.raises(ValueError, match="ARCHIVE_BUSINESS_HASH_INVALID"):
        normalize_manifest_part_hash({
            "hash_algorithm": "sha256", "hash_value": "a" * 32,
        })


def test_streaming_hash_uses_only_the_injected_selected_algorithm(tmp_path):
    target = tmp_path / "SYNTHETIC.rar"
    target.write_bytes(b"SYNTHETIC/SELECTED-HASH-ONLY")
    algorithms: list[str] = []
    opened: list[Path] = []

    def hasher_factory(algorithm: str):
        algorithms.append(algorithm)
        return hashlib.new(algorithm)

    def reader_factory(path: Path):
        opened.append(path)
        return path.open("rb")

    digest = compute_hash_streaming(
        target, tmp_path, "sha256",
        reader_factory=reader_factory, hasher_factory=hasher_factory,
    )

    assert digest == hashlib.sha256(target.read_bytes()).hexdigest()
    assert algorithms == ["sha256"]
    assert opened == [target.resolve()]


def test_discovery_priority_config_then_environment_then_path(tmp_path):
    configured = tmp_path / "configured.exe"
    configured.write_bytes(b"x")
    env_path = tmp_path / "env.exe"
    env_path.write_bytes(b"x")
    calls = []

    def path_lookup(name):
        calls.append(name)
        return str(tmp_path / "path.exe")

    capability = discover_winrar(
        str(configured), env={"BIJI_WINRAR_PATH": str(env_path)},
        path_lookup=path_lookup, probe_runner=probe_ok,
    )
    assert capability.available
    assert capability.executable_path == str(configured)
    assert capability.public_dict()["executable_name"] == "configured.exe"
    assert str(tmp_path) not in str(capability.public_dict())
    assert calls == []


def test_discovery_uses_environment_then_path_and_rejects_directory(tmp_path):
    env_dir = tmp_path / "env-dir"
    env_dir.mkdir()
    path_file = tmp_path / "path.exe"
    path_file.write_bytes(b"x")
    capability = discover_winrar(
        str(env_dir), env={"BIJI_WINRAR_PATH": str(tmp_path / "missing.exe")},
        path_lookup=lambda name: str(path_file), probe_runner=probe_ok,
    )
    assert capability.available
    assert capability.executable_path == str(path_file)


def test_discovery_no_executable_or_failed_probe_is_unavailable(tmp_path):
    bad = tmp_path / "bad.exe"
    bad.write_bytes(b"x")

    def probe_fail(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "C:\\sensitive\\path", "error")

    capability = discover_winrar(str(bad), env={}, path_lookup=lambda name: None, probe_runner=probe_fail)
    assert not capability.available
    assert capability.diagnostic_code == "WINRAR_UNAVAILABLE"
    assert capability.public_dict()["executable_name"] is None


def test_discovery_accepts_rar_volume_help_syntax(tmp_path):
    candidate = tmp_path / "rar.exe"
    candidate.write_bytes(b"synthetic")

    def probe_rar(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "RAR 5.90\nv<size>[k,b]", "")

    capability = discover_winrar(
        str(candidate), env={}, path_lookup=lambda name: None, probe_runner=probe_rar
    )
    assert capability.available
    assert capability.supports_rar_volumes


def test_discovery_winrar_config_prefers_console_sibling_without_gui_probe(tmp_path):
    gui = tmp_path / "WinRAR.exe"
    console = tmp_path / "rar.exe"
    gui.write_bytes(b"gui")
    console.write_bytes(b"console")
    calls = []

    def probe_rar(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "RAR 5.90\nv<size>[k,b]", "")

    capability = discover_winrar(str(gui), env={}, path_lookup=lambda name: None, probe_runner=probe_rar)
    assert capability.executable_name == "rar.exe"
    assert all(args[0].casefold().endswith("rar.exe") for args in calls)
    assert not any("WinRAR.exe".casefold() in str(args[0]).casefold() for args in calls)


def test_manifest_uses_actual_numeric_order_selected_md5_and_disc_date(tmp_path):
    first = tmp_path / "案件.part1.rar"
    second = tmp_path / "案件.part2.rar"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    plan = SimpleNamespace(
        plan_id="plan", archive_base_name="案件", volume_size_bytes=4_000_000_000,
        volume_tier_gb=4, max_part_count=2, total_input_bytes=7_000_000_000,
        first_disc_number="GP20260718-01", expected_disc_numbers=("GP20260718-01", "GP20260718-02"),
    )
    capability = SimpleNamespace(available=True, executable_path="fake", executable_name="WinRAR.exe", version="6.24", supports_rar_volumes=True,
                                 public_dict=lambda: {"available": True, "executable_name": "WinRAR.exe", "version": "6.24", "supports_rar_volumes": True})
    validation = validate_archive_parts(tmp_path, plan, capability, integrity_runner=probe_ok)
    manifest, paths = assemble_archive_manifest(plan, validation, capability, retry_count=0)
    assert [part["part_number"] for part in manifest["parts"]] == [1, 2]
    assert [part["disc_number"] for part in manifest["parts"]] == [
        "GP20260718-01", "GP20260718-02",
    ]
    assert manifest["parts"][0]["filename"] == "案件.part1.rar"
    assert "md5" not in manifest["parts"][0]
    assert manifest["parts"][0]["hash_algorithm"] == "md5"
    assert manifest["parts"][0]["hash_value"] == hashlib.md5(b"first").hexdigest()
    assert manifest["parts"][0]["disc_date"] == "2026-07-18"
    assert all(Path(name).name == name for name in paths)


@pytest.mark.parametrize(
    ("algorithm", "hash_factory"),
    [("sha1", hashlib.sha1), ("sha256", hashlib.sha256)],
)
def test_manifest_writes_only_the_selected_hash(
    tmp_path, algorithm, hash_factory,
):
    part = tmp_path / "SYNTHETIC.rar"
    payload = b"SYNTHETIC/HASH-ALGORITHM"
    part.write_bytes(payload)
    plan = SimpleNamespace(
        plan_id="SYNTHETIC-PLAN", archive_base_name="SYNTHETIC",
        volume_size_bytes=4_000_000_000, volume_tier_gb=4,
        max_part_count=1, total_input_bytes=len(payload),
        first_disc_number="GP20260823-01",
        expected_disc_numbers=("GP20260823-01",),
    )
    capability = SimpleNamespace(
        available=True, executable_path="SYNTHETIC", executable_name="WinRAR.exe",
        version="6.24", supports_rar_volumes=True,
        public_dict=lambda: {"available": True},
    )
    validation = validate_archive_parts(
        tmp_path, plan, capability, integrity_runner=probe_ok,
    )

    manifest, _ = assemble_archive_manifest(
        plan, validation, capability, retry_count=0,
        hash_algorithm=algorithm,
    )

    item = manifest["parts"][0]
    assert "md5" not in item
    assert item["hash_algorithm"] == algorithm
    assert item["hash_value"] == hash_factory(payload).hexdigest()


@pytest.mark.parametrize(
    ("prefix", "expected_prefix"),
    [
        ("G", "G"),
        ("GP", "GP"),
        ("检验盘", "检验盘"),
        ("ABCDEFGHIJKLMNOPQRST", "ABCDEFGHIJKLMNOPQRST"),
        ("检验检验检验检验检验检验检验检验检验检验", "检验检验检验检验检验检验检验检验检验检验"),
    ],
)
def test_manifest_disc_date_uses_parsed_sequence_for_variable_prefixes(
    tmp_path, prefix, expected_prefix,
):
    first = tmp_path / "SYNTHETIC.part1.rar"
    second = tmp_path / "SYNTHETIC.part2.rar"
    first.write_bytes(b"SYNTHETIC-FIRST")
    second.write_bytes(b"SYNTHETIC-SECOND")
    first_disc_number = f"{prefix}20260809-01"
    plan = SimpleNamespace(
        plan_id="SYNTHETIC-PLAN", archive_base_name="SYNTHETIC",
        volume_size_bytes=4_000_000_000, volume_tier_gb=4,
        max_part_count=2, total_input_bytes=4_000_000_001,
        first_disc_number=first_disc_number,
        expected_disc_numbers=(first_disc_number, f"{prefix}20260809-02"),
    )
    capability = SimpleNamespace(
        available=True, executable_path="SYNTHETIC", executable_name="WinRAR.exe",
        version="6.24", supports_rar_volumes=True,
        public_dict=lambda: {
            "available": True, "executable_name": "WinRAR.exe",
            "version": "6.24", "supports_rar_volumes": True,
        },
    )
    validation = validate_archive_parts(
        tmp_path, plan, capability, integrity_runner=probe_ok,
    )

    manifest, _ = assemble_archive_manifest(
        plan, validation, capability, retry_count=0,
    )

    assert [part["disc_number"] for part in manifest["parts"]] == [
        f"{expected_prefix}20260809-01",
        f"{expected_prefix}20260809-02",
    ]
    assert [part["disc_date"] for part in manifest["parts"]] == [
        "2026-08-09", "2026-08-09",
    ]


def test_published_manifest_rejects_disc_mapping_not_contiguous(tmp_path):
    first = tmp_path / "case.part1.rar"
    second = tmp_path / "case.part2.rar"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    manifest = {
        "archive_base_name": "case", "volume_size_bytes": 4_000_000_000,
        "max_part_count": 2, "actual_archive_bytes": 11,
        "parts": [
            {
                "part_number": 1, "filename": first.name, "size_bytes": 5,
                "md5": hashlib.md5(b"first").hexdigest(),
                "disc_number": "GP20260718-02", "disc_date": "2026-07-18",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            },
            {
                "part_number": 2, "filename": second.name, "size_bytes": 6,
                "md5": hashlib.md5(b"second").hexdigest(),
                "disc_number": "GP20260718-01", "disc_date": "2026-07-18",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            },
        ],
    }
    record = SimpleNamespace(final_dir=tmp_path, public_manifest=manifest)

    assert not validate_published_manifest(record)


def test_manifest_uses_actual_part_count_when_less_than_expected(tmp_path):
    part = tmp_path / "案件.part1.rar"
    part.write_bytes(b"one")
    plan = SimpleNamespace(
        plan_id="plan", archive_base_name="案件", volume_size_bytes=10,
        volume_tier_gb=4, max_part_count=2, total_input_bytes=20,
        first_disc_number="GP20260718-01", expected_disc_numbers=("GP20260718-01", "GP20260718-02"),
    )
    capability = SimpleNamespace(available=True, executable_path="fake", executable_name="WinRAR.exe", version="6.24", supports_rar_volumes=True,
                                 public_dict=lambda: {"available": True, "executable_name": "WinRAR.exe", "version": "6.24", "supports_rar_volumes": True})
    validation = validate_archive_parts(tmp_path, plan, capability, integrity_runner=probe_ok)
    manifest, _ = assemble_archive_manifest(plan, validation, capability, retry_count=0)
    assert len(manifest["parts"]) == 1
    assert manifest["parts"][0]["disc_number"] == "GP20260718-01"


def test_published_manifest_detects_modified_part(tmp_path):
    part = tmp_path / "案件.part1.rar"
    part.write_bytes(b"original")
    digest = hashlib.md5(b"original").hexdigest()
    record = SimpleNamespace(
        final_dir=tmp_path,
        public_manifest={
            "archive_base_name": "案件", "volume_size_bytes": 10, "max_part_count": 2,
            "parts": [{"part_number": 1, "filename": part.name, "size_bytes": 8, "md5": digest,
                       "disc_capacity_bytes": 4_000_000_000}],
            "actual_archive_bytes": 8,
        },
    )
    assert validate_published_manifest(record)
    part.write_bytes(b"changed!")
    assert not validate_published_manifest(record)


@pytest.mark.parametrize(
    ("algorithm", "hash_factory"),
    [("md5", hashlib.md5), ("sha1", hashlib.sha1), ("sha256", hashlib.sha256)],
)
def test_manifest_content_gate_rejects_same_size_tamper_for_selected_algorithm(
    tmp_path, algorithm, hash_factory,
):
    part = tmp_path / "SYNTHETIC.rar"
    original = b"SYNTHETIC/ORIGINAL"
    tampered = b"SYNTHETIC/TAMPERED"
    assert len(original) == len(tampered)
    part.write_bytes(original)
    manifest = {
        "manifest_id": "SYNTHETIC-MANIFEST",
        "archive_base_name": "SYNTHETIC",
        "archive_mode": "standard_split",
        "volume_size_bytes": 4 * 1024**3,
        "max_part_count": 1,
        "validation_status": "validated",
        "parts": [{
            "part_number": 1, "filename": part.name, "size_bytes": len(original),
            "hash_algorithm": algorithm, "hash_value": hash_factory(original).hexdigest(),
            "disc_number": "", "disc_date": "",
            "disc_capacity_bytes": 4 * 1024**3,
            "volume_size_bytes": 4 * 1024**3,
        }],
        "actual_archive_bytes": len(original),
    }
    record = SimpleNamespace(
        manifest_id="SYNTHETIC-MANIFEST", final_dir=tmp_path,
        public_manifest=manifest,
    )

    assert validate_manifest_files(record) is None
    part.write_bytes(tampered)
    assert validate_manifest_files(record) == "ARCHIVE_MANIFEST_PART_CHANGED"


def test_manifest_file_validation_hashes_each_part_once(monkeypatch, tmp_path):
    first = tmp_path / "case.part1.rar"
    second = tmp_path / "case.part2.rar"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    manifest = {
        "manifest_id": "manifest-1",
        "validation_status": "validated",
        "parts": [
            {
                "part_number": 1, "filename": first.name, "size_bytes": 5,
                "md5": hashlib.md5(b"first").hexdigest(),
                "disc_number": "GP20260718-01", "disc_date": "2026-07-18",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            },
            {
                "part_number": 2, "filename": second.name, "size_bytes": 6,
                "md5": hashlib.md5(b"second").hexdigest(),
                "disc_number": "GP20260718-02", "disc_date": "2026-07-18",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            },
        ],
        "actual_archive_bytes": 11,
    }
    record = SimpleNamespace(
        manifest_id="manifest-1", final_dir=tmp_path, public_manifest=manifest,
    )
    calls = []

    def counted_hash(path, root, algorithm):
        calls.append((path.name, algorithm))
        return hashlib.new(algorithm, path.read_bytes()).hexdigest()

    monkeypatch.setattr("app.services.archive.archive_manifest_service.compute_hash_streaming", counted_hash)
    assert validate_manifest_files(record) is None
    assert calls == [(first.name, "md5"), (second.name, "md5")]


def test_authenticated_manifest_metadata_does_not_read_part_content(monkeypatch, tmp_path):
    part = tmp_path / "case.rar"
    payload = b"SYNTHETIC/AUTHENTICATED-METADATA"
    part.write_bytes(payload)
    manifest = {
        "manifest_id": "manifest-metadata",
        "archive_base_name": "case",
        "volume_size_bytes": 4_000_000_000,
        "max_part_count": 1,
        "validation_status": "validated",
        "parts": [{
            "part_number": 1, "filename": part.name, "size_bytes": len(payload),
            "md5": hashlib.md5(payload).hexdigest(),
            "disc_number": "", "disc_date": "",
            "disc_capacity_bytes": 4_000_000_000,
            "volume_size_bytes": 4_000_000_000,
        }],
        "actual_archive_bytes": len(payload),
    }
    record = SimpleNamespace(
        manifest_id="manifest-metadata", final_dir=tmp_path, public_manifest=manifest,
    )
    monkeypatch.setattr(
        "app.services.archive.archive_manifest_service.compute_hash_streaming",
        lambda *_args, **_kwargs: pytest.fail("metadata projection read RAR content"),
    )

    assert validate_manifest_metadata(record) is None
    part.write_bytes(b"short")
    assert validate_manifest_metadata(record) == "ARCHIVE_MANIFEST_PART_CHANGED"


def test_same_run_identity_detects_equal_size_change_without_rehash(monkeypatch, tmp_path):
    part = tmp_path / "case.rar"
    payload = b"SYNTHETIC/ORIGINAL"
    part.write_bytes(payload)
    manifest = {
        "manifest_id": "manifest-identity",
        "archive_base_name": "case",
        "volume_size_bytes": 4_000_000_000,
        "max_part_count": 1,
        "validation_status": "validated",
        "parts": [{
            "part_number": 1, "filename": part.name, "size_bytes": len(payload),
            "md5": hashlib.md5(payload).hexdigest(),
            "disc_number": "", "disc_date": "",
            "disc_capacity_bytes": 4_000_000_000,
            "volume_size_bytes": 4_000_000_000,
        }],
        "actual_archive_bytes": len(payload),
    }
    record = SimpleNamespace(
        manifest_id="manifest-identity", final_dir=tmp_path, public_manifest=manifest,
    )
    trusted_hashes = {part.name: manifest["parts"][0]["md5"]}
    identities = capture_archive_file_identities(tmp_path, {part.name})
    monkeypatch.setattr(
        "app.services.archive.archive_manifest_service.compute_hash_streaming",
        lambda *_args, **_kwargs: pytest.fail("same-run validation rehashed content"),
    )

    assert validate_manifest_files(
        record, verified_hashes=trusted_hashes,
        verified_file_identities=identities,
    ) is None
    part.write_bytes(b"SYNTHETIC/TAMPERED")
    assert validate_manifest_files(
        record, verified_hashes=trusted_hashes,
        verified_file_identities=identities,
    ) == "ARCHIVE_MANIFEST_PART_CHANGED"


# ─── 光盘容量计算 ──────────────────────────────────────────────────────

class TestComputeDiscCapacity:
    """光盘容量档位选择的纯函数边界测试。"""

    def test_minimal_size_returns_smallest_tier(self):
        assert compute_disc_capacity(1) == 4 * 1024**3

    def test_exact_tier_boundary(self):
        assert compute_disc_capacity(4 * 1024**3) == 4 * 1024**3
        assert compute_disc_capacity(22 * 1024**3) == 22 * 1024**3
        assert compute_disc_capacity(45 * 1024**3) == 45 * 1024**3

    def test_just_above_tier_boundary(self):
        assert compute_disc_capacity(4 * 1024**3 + 1) == 22 * 1024**3
        assert compute_disc_capacity(22 * 1024**3 + 1) == 45 * 1024**3

    def test_typical_sizes(self):
        # 9 GB → 22 GB 光盘
        assert compute_disc_capacity(9 * 1024**3) == 22 * 1024**3
        # 2 GB → 4 GB 光盘（47 GB 场景的尾部分卷）
        assert compute_disc_capacity(2 * 1024**3) == 4 * 1024**3

    def test_max_capacity(self):
        assert compute_disc_capacity(45 * 1024**3) == 45 * 1024**3

    def test_exceeds_max_capacity(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            compute_disc_capacity(45 * 1024**3 + 1)

    def test_zero_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            compute_disc_capacity(0)

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            compute_disc_capacity(-1)

    def test_boolean_raises(self):
        with pytest.raises(ValueError, match="must be an integer"):
            compute_disc_capacity(True)
        with pytest.raises(ValueError, match="must be an integer"):
            compute_disc_capacity(False)

    def test_float_raises(self):
        with pytest.raises(ValueError, match="must be an integer"):
            compute_disc_capacity(100.0)


class TestDiscCapacityInManifest:
    """验证 disc_capacity_bytes 能正确组装和校验。"""

    def test_manifest_parts_receive_independent_capacity(self, tmp_path):
        """每个分卷获得自身的光盘容量，而不是档位值。"""
        from app.repository.archive.archive_validator_repository import (
            ValidatedArchivePart,
            ArchiveValidationResult,
        )
        from app.repository.archive.winrar_discovery_repository import WinRarCapability
        from app.services.archive.archive_planner_service import (
            ArchiveDiagnostic,
            ArchivePlan,
            ArchiveSourceEntry,
        )

        staging = tmp_path / "staging"
        staging.mkdir()
        part1 = staging / "case.part1.rar"
        part2 = staging / "case.part2.rar"
        part1.write_bytes(b"A" * 100)
        part2.write_bytes(b"B" * 50)

        plan = ArchivePlan(
            plan_id="plan-1",
            case_display_name="测试",
            archive_base_name="case",
            source_entries=(ArchiveSourceEntry("a.dat", 100, 0),),
            total_input_bytes=150,
            volume_size_bytes=4_000_000_000,
            volume_tier_gb=4,
            expected_part_count=2,
            max_part_count=2,
            first_disc_number="GP20260718-001",
            expected_disc_numbers=("GP20260718-001", "GP20260718-002"),
            max_replan_attempts=2,
            status="planned",
            diagnostics=(),
        )
        validation = ArchiveValidationResult(
            valid=True,
            parts=(
                ValidatedArchivePart(1, "case.part1.rar", part1, 100),
                ValidatedArchivePart(2, "case.part2.rar", part2, 50),
            ),
        )
        capability = WinRarCapability(
            available=True,
            executable_path=str(tmp_path / "winrar.exe"),
            executable_name="WinRAR.exe",
            version="6.24",
            supports_rar_volumes=True,
        )

        manifest, _paths = assemble_archive_manifest(plan, validation, capability, retry_count=0)

        parts = manifest["parts"]
        assert len(parts) == 2
        # 两个分卷都能装入 4 GB 光盘
        assert parts[0]["disc_capacity_bytes"] == 4 * 1024**3
        assert parts[1]["disc_capacity_bytes"] == 4 * 1024**3
        # volume_size_bytes 是继承的档位上限
        assert parts[0]["volume_size_bytes"] == 4_000_000_000
        assert parts[1]["volume_size_bytes"] == 4_000_000_000

    def test_oversized_single_manifest_has_explicit_mode_without_disc_capacity(
        self, tmp_path,
    ):
        from app.repository.archive.archive_validator_repository import (
            ArchiveValidationResult,
            ValidatedArchivePart,
        )

        part = tmp_path / "case.rar"
        part.write_bytes(b"SYNTHETIC-OVERSIZED-SINGLE")
        plan = SimpleNamespace(
            plan_id="plan-oversized", archive_base_name="case",
            archive_mode="oversized_single_volume", volume_size_bytes=None,
            volume_tier_gb=None, max_part_count=1,
            total_input_bytes=225 * 1024**3 + 1,
            first_disc_number="GP20260718-001",
        )
        validation = ArchiveValidationResult(
            valid=True,
            parts=(ValidatedArchivePart(1, part.name, part, part.stat().st_size),),
        )

        manifest, _paths = assemble_archive_manifest(
            plan, validation,
            WinRarCapability(True, "fake-winrar", "WinRAR.exe", "6.24", True),
            retry_count=0,
        )
        record = SimpleNamespace(
            manifest_id=manifest["manifest_id"], final_dir=tmp_path,
            public_manifest=manifest,
        )

        assert manifest["archive_mode"] == "oversized_single_volume"
        assert manifest["volume_size_bytes"] is None
        assert "disc_capacity_bytes" not in manifest["parts"][0]
        assert validate_manifest_files(record) is None

    def test_tampered_capacity_rejected(self, tmp_path):
        """disc_capacity_bytes 与实际大小不匹配时 MUST 校验失败。"""
        part = tmp_path / "case.part1.rar"
        part.write_bytes(b"X" * 10)
        digest = hashlib.md5(b"X" * 10).hexdigest()
        # size=10 应得到 disc_capacity=4GB，但这里注入错误值
        record = SimpleNamespace(
            final_dir=tmp_path,
            public_manifest={
                "manifest_id": "M-1",
                "archive_base_name": "case",
                "volume_size_bytes": 10_000_000,
                "max_part_count": 2,
                "parts": [{
                    "part_number": 1, "filename": part.name,
                    "size_bytes": 10, "md5": digest,
                    "disc_capacity_bytes": 22_000_000_000,  # 错误：应为 4 GB
                    "volume_size_bytes": 10_000_000,
                }],
                "actual_archive_bytes": 10,
            },
        )
        assert not validate_published_manifest(record)

    def test_capacity_absent_derives_from_size_bytes(self, tmp_path):
        """缺少 disc_capacity_bytes 时，根据可信 size_bytes 推导（兼容旧版 manifest）。"""
        part = tmp_path / "case.part1.rar"
        part.write_bytes(b"Y" * 20)
        digest = hashlib.md5(b"Y" * 20).hexdigest()
        record = SimpleNamespace(
            final_dir=tmp_path,
            manifest_id="M-cap",
            public_manifest={
                "manifest_id": "M-cap",
                "validation_status": "validated",
                "parts": [{
                    "part_number": 1, "filename": part.name,
                    "size_bytes": 20, "md5": digest,
                    "disc_number": "GP20260718-01", "disc_date": "2026-07-18",
                    # 有意省略 disc_capacity_bytes（旧版 manifest）
                }],
                "actual_archive_bytes": 20,
            },
        )
        assert validate_manifest_files(record) is None

    def test_old_manifest_without_disc_capacity_still_validates(self, tmp_path):
        """旧版 manifest 缺少 disc_capacity_bytes 时，根据可信 size_bytes 推导。"""
        part = tmp_path / "case.part1.rar"
        part.write_bytes(b"P" * 50)
        digest = hashlib.md5(b"P" * 50).hexdigest()
        record = SimpleNamespace(
            final_dir=tmp_path,
            manifest_id="M-old",
            public_manifest={
                "manifest_id": "M-old",
                "validation_status": "validated",
                "volume_size_bytes": 4_000_000_000,
                "parts": [{
                    "part_number": 1, "filename": part.name,
                    "size_bytes": 50, "md5": digest,
                    "disc_number": "GP20260718-01", "disc_date": "2026-07-18",
                    "volume_size_bytes": 4_000_000_000,
                    # 有意省略 disc_capacity_bytes（旧版 manifest）
                }],
                "actual_archive_bytes": 50,
            },
        )
        # 应通过：disc_capacity 根据 size_bytes 推导
        assert validate_manifest_files(record) is None

    def test_volume_size_invariant_rejects_part_mismatch(self, tmp_path):
        """分卷存在 volume_size_bytes 时，必须等于 manifest 的对应值。"""
        part = tmp_path / "case.part1.rar"
        part.write_bytes(b"Z" * 30)
        digest = hashlib.md5(b"Z" * 30).hexdigest()
        record = SimpleNamespace(
            final_dir=tmp_path,
            manifest_id="M-inv",
            public_manifest={
                "manifest_id": "M-inv",
                "validation_status": "validated",
                "volume_size_bytes": 4_000_000_000,
                "parts": [{
                    "part_number": 1, "filename": part.name,
                    "size_bytes": 30, "md5": digest,
                    "disc_number": "GP20260718-01", "disc_date": "2026-07-18",
                    "disc_capacity_bytes": 4_000_000_000,
                    "volume_size_bytes": 22_000_000_000,  # 不匹配
                }],
                "actual_archive_bytes": 30,
            },
        )
        assert validate_manifest_files(record) == "ARCHIVE_MANIFEST_INVALID"

    def test_mixed_capacity_parts_get_independent_disc_sizes(self, tmp_path):
        """分卷 [22 GB, 1 GB] 应得到光盘容量 [22 GB, 4 GB]。"""
        part1 = tmp_path / "case.part1.rar"
        part2 = tmp_path / "case.part2.rar"
        part1.write_bytes(b"X" * 100)
        part2.write_bytes(b"Y" * 50)
        from app.repository.archive.archive_validator_repository import (
            ValidatedArchivePart, ArchiveValidationResult,
        )
        from app.repository.archive.winrar_discovery_repository import WinRarCapability
        from app.services.archive.archive_planner_service import (
            ArchiveDiagnostic, ArchivePlan, ArchiveSourceEntry,
        )
        plan = ArchivePlan(
            plan_id="plan-mix",
            case_display_name="测试",
            archive_base_name="case",
            source_entries=(ArchiveSourceEntry("a.dat", 22_000_000_000 + 1_000_000_000, 0),),
            total_input_bytes=23_000_000_000,
            volume_size_bytes=22_000_000_000,
            volume_tier_gb=22,
            expected_part_count=2,
            max_part_count=2,
            first_disc_number="GP20260718-001",
            expected_disc_numbers=("GP20260718-001", "GP20260718-002"),
            max_replan_attempts=2,
            status="planned",
            diagnostics=(),
        )
        validation = ArchiveValidationResult(
            valid=True,
            parts=(
                ValidatedArchivePart(1, "case.part1.rar", part1, 22_000_000_000),
                ValidatedArchivePart(2, "case.part2.rar", part2, 1_000_000_000),
            ),
        )
        capability = WinRarCapability(
            available=True,
            executable_path=str(tmp_path / "winrar.exe"),
            executable_name="WinRAR.exe",
            version="6.24",
            supports_rar_volumes=True,
        )
        manifest, _paths = assemble_archive_manifest(plan, validation, capability, retry_count=0)
        parts = manifest["parts"]
        assert parts[0]["disc_capacity_bytes"] == 22 * 1024**3
        assert parts[1]["disc_capacity_bytes"] == 4 * 1024**3
        # volume_size_bytes 是档位上限，所有分卷均相同
        assert parts[0]["volume_size_bytes"] == 22_000_000_000
        assert parts[1]["volume_size_bytes"] == 22_000_000_000

    def test_45gb_tier_mixed_capacity_parts(self, tmp_path):
        """45 GB 档位的分卷 [45 GB, 2 GB] 应得到光盘容量 [45 GB, 4 GB]。"""
        part1 = tmp_path / "case.part1.rar"
        part2 = tmp_path / "case.part2.rar"
        part1.write_bytes(b"A" * 200)
        part2.write_bytes(b"B" * 100)
        from app.repository.archive.archive_validator_repository import (
            ValidatedArchivePart, ArchiveValidationResult,
        )
        from app.repository.archive.winrar_discovery_repository import WinRarCapability
        from app.services.archive.archive_planner_service import (
            ArchiveDiagnostic, ArchivePlan, ArchiveSourceEntry,
        )
        plan = ArchivePlan(
            plan_id="plan-45",
            case_display_name="测试45",
            archive_base_name="case",
            source_entries=(ArchiveSourceEntry("a.dat", 47_000_000_000, 0),),
            total_input_bytes=47_000_000_000,
            volume_size_bytes=45_000_000_000,
            volume_tier_gb=45,
            expected_part_count=2,
            max_part_count=3,
            first_disc_number="GP20260718-001",
            expected_disc_numbers=("GP20260718-001", "GP20260718-002"),
            max_replan_attempts=2,
            status="planned",
            diagnostics=(),
        )
        validation = ArchiveValidationResult(
            valid=True,
            parts=(
                ValidatedArchivePart(1, "case.part1.rar", part1, 45_000_000_000),
                ValidatedArchivePart(2, "case.part2.rar", part2, 2_000_000_000),
            ),
        )
        capability = WinRarCapability(
            available=True,
            executable_path=str(tmp_path / "winrar.exe"),
            executable_name="WinRAR.exe",
            version="6.24",
            supports_rar_volumes=True,
        )
        manifest, _paths = assemble_archive_manifest(plan, validation, capability, retry_count=0)
        parts = manifest["parts"]
        assert parts[0]["disc_capacity_bytes"] == 45 * 1024**3
        assert parts[1]["disc_capacity_bytes"] == 4 * 1024**3
        assert parts[0]["volume_size_bytes"] == 45_000_000_000
        assert parts[1]["volume_size_bytes"] == 45_000_000_000
