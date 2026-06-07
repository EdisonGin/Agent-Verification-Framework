"""Filesystem-backed results store for trace, verification, metrics, reports, and manifests."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from avf.contracts import MetricResult, RunConfig, RunTrace, ValidationError, VerificationResult
from avf.metrics.writer import MetricResultWriter
from avf.reporting.markdown import MarkdownReportWriter
from avf.tracing.writer import TraceWriter
from avf.verification import DEFAULT_RULE_BASED_VERIFIER_ID
from avf.verification.writer import VerificationResultWriter


ARTIFACT_MANIFEST_VERSION = "1.0"
RESULT_STORE_RERUN_POLICY = "deterministic_overwrite"
_REPORT_RUN_ID_PATTERN = re.compile(r"\|\s*Run ID\s*\|\s*`([^`]+)`\s*\|")


@dataclass(frozen=True)
class ResultsStoreLayout:
    """Directory layout for one filesystem-backed results store."""

    artifact_root: Path
    trace_dir: Path
    result_dir: Path
    report_dir: Path
    manifest_dir: Path


@dataclass(frozen=True)
class ArtifactRecord:
    """Stable integrity record for one persisted artifact."""

    name: str
    path: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class ArtifactValidationResult:
    """Validation result for one run's artifact set."""

    run_id: str
    passed: bool
    issues: List[str]
    artifacts: Dict[str, ArtifactRecord]

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "passed": self.passed,
            "issues": list(self.issues),
            "artifacts": {
                name: record.to_dict()
                for name, record in sorted(self.artifacts.items())
            },
        }


@dataclass(frozen=True)
class ArtifactManifest:
    """Deterministic manifest for one validated artifact set."""

    schema_version: str
    manifest_version: str
    run_id: str
    rerun_policy: str
    validation: ArtifactValidationResult

    def to_dict(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "manifest_version": self.manifest_version,
            "run_id": self.run_id,
            "rerun_policy": self.rerun_policy,
            "validation": self.validation.to_dict(),
        }


class FileSystemResultsStore:
    """Write Phase 1/2 artifacts using the current filesystem results store."""

    def __init__(self, layout: ResultsStoreLayout) -> None:
        self.layout = layout

    @classmethod
    def from_run_config(cls, run_config: RunConfig, artifact_root: Optional[Path] = None) -> "FileSystemResultsStore":
        if artifact_root is not None:
            return cls.from_artifact_root(Path(artifact_root))

        trace_dir = Path(str(run_config.artifacts.get("trace_dir", "artifacts/traces")))
        result_dir = Path(str(run_config.artifacts.get("result_dir", "artifacts/results")))
        report_dir = Path(str(run_config.artifacts.get("report_dir", "artifacts/reports")))
        artifact_root_path = _common_artifact_root(trace_dir, result_dir, report_dir)
        manifest_dir = Path(str(run_config.artifacts.get("manifest_dir", artifact_root_path / "manifests")))
        return cls(
            ResultsStoreLayout(
                artifact_root=artifact_root_path,
                trace_dir=trace_dir,
                result_dir=result_dir,
                report_dir=report_dir,
                manifest_dir=manifest_dir,
            )
        )

    @classmethod
    def from_artifact_root(cls, artifact_root: Path) -> "FileSystemResultsStore":
        root = Path(artifact_root)
        return cls(
            ResultsStoreLayout(
                artifact_root=root,
                trace_dir=root / "traces",
                result_dir=root / "results",
                report_dir=root / "reports",
                manifest_dir=root / "manifests",
            )
        )

    def trace_path(self, run_id: str) -> Path:
        return TraceWriter(self.layout.trace_dir).path_for(run_id)

    def verification_path(self, result: VerificationResult) -> Path:
        return VerificationResultWriter(self.layout.result_dir).path_for(result)

    def metrics_path(self, result: MetricResult) -> Path:
        return MetricResultWriter(self.layout.result_dir).path_for(result)

    def report_path(self, run_id: str) -> Path:
        return MarkdownReportWriter(self.layout.report_dir).path_for(run_id)

    def manifest_path(self, run_id: str) -> Path:
        return self.layout.manifest_dir / f"{run_id}.manifest.json"

    def artifact_paths_for_run(
        self,
        run_id: str,
        verifier_id: str = DEFAULT_RULE_BASED_VERIFIER_ID,
    ) -> Dict[str, Path]:
        return {
            "trace": self.trace_path(run_id),
            "verification": self.layout.result_dir / f"{run_id}.{verifier_id}.json",
            "metrics": self.layout.result_dir / f"{run_id}.metrics.json",
            "report": self.report_path(run_id),
        }

    def write_trace(self, trace: RunTrace) -> Path:
        return TraceWriter(self.layout.trace_dir).write(trace)

    def write_verification_result(self, result: VerificationResult) -> Path:
        return VerificationResultWriter(self.layout.result_dir).write(result)

    def write_metric_result(self, result: MetricResult) -> Path:
        return MetricResultWriter(self.layout.result_dir).write(result)

    def write_report(self, run_id: str, content: str) -> Path:
        return MarkdownReportWriter(self.layout.report_dir).write(run_id, content)

    def validate_run_artifacts(
        self,
        run_id: str,
        verifier_id: str = DEFAULT_RULE_BASED_VERIFIER_ID,
    ) -> ArtifactValidationResult:
        paths = self.artifact_paths_for_run(run_id, verifier_id)
        issues: List[str] = []
        records: Dict[str, ArtifactRecord] = {}
        observed_run_ids: Dict[str, str] = {}

        for name, path in sorted(paths.items()):
            if not path.exists():
                issues.append(f"Missing {name} artifact: {self.relative_path(path)}")
                continue

            try:
                records[name] = self._artifact_record(name, path)
            except OSError as exc:
                issues.append(f"Could not read {name} artifact {self.relative_path(path)}: {exc}")
                continue

            artifact_run_id = self._artifact_run_id(name, path, issues)
            if artifact_run_id is None:
                continue
            observed_run_ids[name] = artifact_run_id
            if artifact_run_id != run_id:
                issues.append(
                    f"{name} artifact run_id mismatch: expected {run_id}, found {artifact_run_id}"
                )

        distinct_run_ids = sorted(set(observed_run_ids.values()))
        if len(distinct_run_ids) > 1:
            joined = ", ".join(f"{name}={value}" for name, value in sorted(observed_run_ids.items()))
            issues.append(f"Artifact run_id values do not agree: {joined}")

        return ArtifactValidationResult(
            run_id=run_id,
            passed=not issues,
            issues=issues,
            artifacts=records,
        )

    def build_artifact_manifest(
        self,
        run_id: str,
        verifier_id: str = DEFAULT_RULE_BASED_VERIFIER_ID,
    ) -> ArtifactManifest:
        return ArtifactManifest(
            schema_version="1.0",
            manifest_version=ARTIFACT_MANIFEST_VERSION,
            run_id=run_id,
            rerun_policy=RESULT_STORE_RERUN_POLICY,
            validation=self.validate_run_artifacts(run_id, verifier_id),
        )

    def write_artifact_manifest(self, manifest: ArtifactManifest, path: Optional[Path] = None) -> Path:
        output_path = Path(path) if path is not None else self.manifest_path(manifest.run_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        return output_path

    def relative_paths(self, paths: Mapping[str, Path]) -> Dict[str, str]:
        values: Dict[str, str] = {}
        for name, path in paths.items():
            values[name] = self.relative_path(path)
        return values

    def relative_path(self, path: Path) -> str:
        try:
            return str(Path(path).relative_to(self.layout.artifact_root))
        except ValueError:
            return str(path)

    def _artifact_record(self, name: str, path: Path) -> ArtifactRecord:
        payload = path.read_bytes()
        return ArtifactRecord(
            name=name,
            path=self.relative_path(path),
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        )

    def _artifact_run_id(self, name: str, path: Path, issues: List[str]) -> Optional[str]:
        if name == "trace":
            payload = self._read_json_object(name, path, issues)
            if payload is None:
                return None
            try:
                return RunTrace.from_dict(payload).run_id
            except ValidationError as exc:
                issues.append(f"Invalid trace artifact {self.relative_path(path)}: {exc}")
                return None

        if name == "verification":
            payload = self._read_json_object(name, path, issues)
            if payload is None:
                return None
            try:
                return VerificationResult.from_dict(payload).run_id
            except ValidationError as exc:
                issues.append(f"Invalid verification artifact {self.relative_path(path)}: {exc}")
                return None

        if name == "metrics":
            payload = self._read_json_object(name, path, issues)
            if payload is None:
                return None
            try:
                return MetricResult.from_dict(payload).run_id
            except ValidationError as exc:
                issues.append(f"Invalid metrics artifact {self.relative_path(path)}: {exc}")
                return None

        if name == "report":
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                issues.append(f"Could not read report artifact {self.relative_path(path)}: {exc}")
                return None
            match = _REPORT_RUN_ID_PATTERN.search(content)
            if not match:
                issues.append(f"Report artifact does not declare a Run ID: {self.relative_path(path)}")
                return None
            return match.group(1)

        issues.append(f"Unsupported artifact type for validation: {name}")
        return None

    def _read_json_object(self, name: str, path: Path, issues: List[str]) -> Optional[Dict[str, Any]]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            issues.append(f"Invalid {name} JSON artifact {self.relative_path(path)}: {exc}")
            return None
        if not isinstance(payload, dict):
            issues.append(f"Invalid {name} artifact {self.relative_path(path)}: expected a JSON object")
            return None
        return payload


def _common_artifact_root(*paths: Path) -> Path:
    parts = [path.parts for path in paths if path.parts]
    if not parts:
        return Path(".")
    shared = []
    for index, part in enumerate(parts[0]):
        if all(len(candidate) > index and candidate[index] == part for candidate in parts):
            shared.append(part)
        else:
            break
    return Path(*shared) if shared else Path(".")
