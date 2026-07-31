from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ALLOWED_TREATMENTS = frozenset({"DIRECT", "AIOS"})
ALLOWED_API_MODES = frozenset({"OPENAI_RESPONSES_FC"})
ALLOWED_EFFECTS = frozenset({"REMOTE_MODEL_INFERENCE"})


class SubjectRegistryError(ValueError):
    """Raised when a benchmark subject registry is malformed or unsafe."""


@dataclass(frozen=True)
class BenchmarkSubject:
    id: str
    benchmark_id: str
    treatment: str
    provider: str
    model_env: str
    credential_env: str
    api_mode: str
    profile_id: str | None
    profile_path: str | None
    profile_sha256: str | None
    allowed_effects: tuple[str, ...]
    store: bool

    @property
    def uses_profile(self) -> bool:
        return self.profile_path is not None

    def resolve_profile_path(self, repository_root: Path) -> Path | None:
        if self.profile_path is None:
            return None
        return (repository_root / self.profile_path).resolve()

    def verify_profile(self, repository_root: Path) -> dict[str, object]:
        path = self.resolve_profile_path(repository_root)
        if path is None:
            return {
                "profile_present": False,
                "profile_hash_valid": self.profile_sha256 is None,
                "profile_path": None,
                "profile_sha256": None,
            }
        if not path.is_file():
            return {
                "profile_present": False,
                "profile_hash_valid": False,
                "profile_path": str(path),
                "profile_sha256": self.profile_sha256,
            }
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "profile_present": True,
            "profile_hash_valid": observed == self.profile_sha256,
            "profile_path": str(path),
            "profile_sha256": observed,
        }

    def admission(
        self,
        *,
        repository_root: Path,
        environ: Mapping[str, str],
        resource_acknowledged: bool,
        case_shard_resolved: bool,
    ) -> dict[str, object]:
        model_value = environ.get(self.model_env, "").strip()
        credential_present = bool(environ.get(self.credential_env))
        profile = self.verify_profile(repository_root)
        ready = all(
            (
                bool(model_value),
                credential_present,
                resource_acknowledged,
                case_shard_resolved,
                bool(profile["profile_hash_valid"]),
            )
        )
        return {
            "subject_id": self.id,
            "treatment": self.treatment,
            "model_env": self.model_env,
            "model_resolved": bool(model_value),
            "credential_env": self.credential_env,
            "credential_present": credential_present,
            "resource_acknowledged": resource_acknowledged,
            "case_shard_resolved": case_shard_resolved,
            **profile,
            "execution_admission_ready": ready,
            "score_status": "NOT_EXECUTED",
        }


@dataclass(frozen=True)
class SubjectRegistry:
    version: str
    hash_algorithm: str
    subjects: tuple[BenchmarkSubject, ...]
    path: Path
    repository_root: Path

    def by_id(self, subject_id: str) -> BenchmarkSubject:
        for subject in self.subjects:
            if subject.id == subject_id:
                return subject
        raise KeyError(subject_id)

    def pair_for(self, benchmark_id: str) -> tuple[BenchmarkSubject, BenchmarkSubject]:
        matches = [item for item in self.subjects if item.benchmark_id == benchmark_id]
        direct = [item for item in matches if item.treatment == "DIRECT"]
        aios = [item for item in matches if item.treatment == "AIOS"]
        if len(direct) != 1 or len(aios) != 1:
            raise SubjectRegistryError(
                f"{benchmark_id} must define exactly one DIRECT and one AIOS subject"
            )
        pair = (direct[0], aios[0])
        validate_pair(*pair)
        return pair


def _required_text(item: dict[str, object], field: str, subject_id: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SubjectRegistryError(f"{subject_id}.{field} must be a non-empty string")
    return value.strip()


def _optional_text(
    item: dict[str, object], field: str, subject_id: str
) -> str | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SubjectRegistryError(
            f"{subject_id}.{field} must be null or a non-empty string"
        )
    return value.strip()


def _parse_subject(item: object) -> BenchmarkSubject:
    if not isinstance(item, dict):
        raise SubjectRegistryError("each subject must be an object")
    subject_id = _required_text(item, "id", "<unknown>")
    treatment = _required_text(item, "treatment", subject_id)
    if treatment not in ALLOWED_TREATMENTS:
        raise SubjectRegistryError(
            f"{subject_id}.treatment is unsupported: {treatment}"
        )
    api_mode = _required_text(item, "api_mode", subject_id)
    if api_mode not in ALLOWED_API_MODES:
        raise SubjectRegistryError(f"{subject_id}.api_mode is unsupported: {api_mode}")
    effects = item.get("allowed_effects")
    if not isinstance(effects, list) or not effects:
        raise SubjectRegistryError(
            f"{subject_id}.allowed_effects must be a non-empty list"
        )
    normalized_effects: list[str] = []
    for effect in effects:
        if not isinstance(effect, str) or effect not in ALLOWED_EFFECTS:
            raise SubjectRegistryError(
                f"{subject_id}.allowed_effects contains unsupported value: {effect!r}"
            )
        normalized_effects.append(effect)
    store = item.get("store")
    if store is not False:
        raise SubjectRegistryError(f"{subject_id}.store must be false")
    profile_id = _optional_text(item, "profile_id", subject_id)
    profile_path = _optional_text(item, "profile_path", subject_id)
    profile_sha256 = _optional_text(item, "profile_sha256", subject_id)
    if treatment == "DIRECT":
        if any(
            value is not None for value in (profile_id, profile_path, profile_sha256)
        ):
            raise SubjectRegistryError(
                f"{subject_id} DIRECT subject may not declare a profile"
            )
    else:
        if not all(
            value is not None for value in (profile_id, profile_path, profile_sha256)
        ):
            raise SubjectRegistryError(
                f"{subject_id} AIOS subject requires profile_id, profile_path, and profile_sha256"
            )
        if len(profile_sha256 or "") != 64 or any(
            ch not in "0123456789abcdef" for ch in profile_sha256 or ""
        ):
            raise SubjectRegistryError(
                f"{subject_id}.profile_sha256 must be a lowercase SHA-256 digest"
            )
    return BenchmarkSubject(
        id=subject_id,
        benchmark_id=_required_text(item, "benchmark_id", subject_id),
        treatment=treatment,
        provider=_required_text(item, "provider", subject_id),
        model_env=_required_text(item, "model_env", subject_id),
        credential_env=_required_text(item, "credential_env", subject_id),
        api_mode=api_mode,
        profile_id=profile_id,
        profile_path=profile_path,
        profile_sha256=profile_sha256,
        allowed_effects=tuple(normalized_effects),
        store=False,
    )


def validate_pair(direct: BenchmarkSubject, aios: BenchmarkSubject) -> None:
    if direct.treatment != "DIRECT" or aios.treatment != "AIOS":
        raise SubjectRegistryError("paired subjects must be ordered DIRECT then AIOS")
    invariant_fields = (
        "benchmark_id",
        "provider",
        "model_env",
        "credential_env",
        "api_mode",
        "allowed_effects",
        "store",
    )
    mismatches = [
        field
        for field in invariant_fields
        if getattr(direct, field) != getattr(aios, field)
    ]
    if mismatches:
        raise SubjectRegistryError(
            f"paired subject invariants differ: {', '.join(mismatches)}"
        )


def load_subject_registry(
    path: Path = Path("benchmarks/subjects.v0.1.json"),
) -> SubjectRegistry:
    path = Path(path)
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SubjectRegistryError(f"cannot load subject registry: {exc}") from exc
    if not isinstance(payload, dict):
        raise SubjectRegistryError("subject registry root must be an object")
    version = payload.get("registry_version")
    if not isinstance(version, str) or not version.strip():
        raise SubjectRegistryError("registry_version must be a non-empty string")
    hash_algorithm = payload.get("hash_algorithm")
    if hash_algorithm != "sha256":
        raise SubjectRegistryError("hash_algorithm must be sha256")
    raw_subjects = payload.get("subjects")
    if not isinstance(raw_subjects, list) or not raw_subjects:
        raise SubjectRegistryError("subjects must be a non-empty list")
    subjects = tuple(_parse_subject(item) for item in raw_subjects)
    ids = [item.id for item in subjects]
    if len(set(ids)) != len(ids):
        raise SubjectRegistryError("subject ids must be unique")
    repository_root = path.resolve().parent.parent
    registry = SubjectRegistry(
        version=version,
        hash_algorithm=hash_algorithm,
        subjects=subjects,
        path=path.resolve(),
        repository_root=repository_root,
    )
    benchmark_ids = {item.benchmark_id for item in subjects}
    for benchmark_id in benchmark_ids:
        registry.pair_for(benchmark_id)
    for subject in subjects:
        verification = subject.verify_profile(repository_root)
        if subject.uses_profile and not verification["profile_present"]:
            raise SubjectRegistryError(f"{subject.id} profile file is missing")
        if not verification["profile_hash_valid"]:
            raise SubjectRegistryError(
                f"{subject.id} profile hash does not match registry"
            )
    return registry
