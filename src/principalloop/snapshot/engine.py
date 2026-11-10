"""Capture, served reads and premise validation. No model engine.

Every mutation goes through the owning Store transaction.
Evidence-check callbacks are reserved for the trusted verifier.
"""

from dataclasses import asdict
from datetime import timezone
import json

from ..domain.contracts import validate_contract
from ..domain.types import Role
from ..store.errors import StoreError
from ..store.sqlite import canonical
from .files import MAX_FILES, MAX_TOTAL, digest, read_checked
from .types import DEPENDENCIES, Document, identifier, references


class Snapshots:
    def __init__(self, store):
        self.store = store
        self.sql = store._connection

    def _authorize(self, principal, roles):
        self.store._guard()
        if not hasattr(self.store, "_write"):
            raise StoreError("READ_ONLY", "Use the single Store owner for mutations")
        if principal.role not in roles or principal.project_id != self.store.plan().project_id:
            raise StoreError("UNAUTHORIZED", "Context does not authorize this operation")

    def _mutate(self, operation, body, principal, event_id, prepare, persist):
        if not hasattr(self.store, "_write"):
            raise StoreError("READ_ONLY", "Use the single Store owner for mutations")
        return self.store._write(operation, event_id, {"project_id": principal.project_id, **body}, principal,
                                 _prepare=prepare, _persist=persist)

    def _prior(self, operation, body, principal, event_id):
        """Resolve a lost acknowledgement before repeating a capture or a check."""
        identifier(event_id)
        row = self.sql.execute("SELECT request_json,outcome_json FROM events WHERE project_id=? AND producer_key=? AND event_id=?",
                               (principal.project_id, canonical([principal.actor_id, principal.run_id]), event_id)).fetchone()
        if not row:
            return None
        request = {"storage_version": 1, "operation": operation, "body": {"project_id": principal.project_id, **body},
                   "principal": {"actor_id": principal.actor_id, "role": principal.role,
                                 "run_id": principal.run_id, "project_id": principal.project_id}}
        if row[0] != canonical(request):
            raise StoreError("ID_CONFLICT", "Same command identity has different content")
        return json.loads(row[1])

    def objects(self):
        self.store._guard()
        return {row["object_id"]: {"object_id": row["object_id"], "revision": row["revision"], "title": row["title"],
                                  "sha256": row["sha256"], "document": json.loads(row["body_json"]),
                                  "author": row["actor_id"], "author_role": row["actor_role"]}
                for row in self.sql.execute("SELECT h.object_id,h.revision,h.title,r.body_json,r.sha256,r.actor_id,r.actor_role "
                                            "FROM object_heads h JOIN object_revisions r USING(object_id,revision)")}

    def history(self, object_id):
        return [{"revision": row[0], "document": json.loads(row[1]), "sha256": row[2], "author": row[3]}
                for row in self.sql.execute("SELECT revision,body_json,sha256,actor_id FROM object_revisions WHERE object_id=? ORDER BY revision", (object_id,))]

    @staticmethod
    def _closure(ids, objects):
        found = set()
        pending = list(ids)
        while pending:
            item = pending.pop()
            if item in found:
                continue
            if item not in objects:
                raise StoreError("UNKNOWN_REFERENCE", f"Unknown object: {item}")
            found.add(item)
            pending.extend(target for relation, target in objects[item]["document"]["links"] if relation in DEPENDENCIES)
        return found

    def put_object(self, document: Document, principal, *, expected_revision: int, event_id: str):
        self._authorize(principal, {Role.HUMAN, Role.EXECUTOR, Role.DIRECTOR, Role.KERNEL})
        if principal.role == Role.DIRECTOR and document.kind not in {"HYPOTHESIS", "QUESTION", "OBSERVATION"}:
            raise StoreError("UNAUTHORIZED", "Director patches are limited to hypotheses, questions and observations")
        if document.kind in {"GOAL", "CONSTRAINT"} and principal.role != Role.HUMAN:
            raise StoreError("UNAUTHORIZED", "Human documentary constraints cannot be edited by an agent")
        if type(expected_revision) is not int or expected_revision < 0:
            raise StoreError("INVALID_REVISION", "Expected revision must be a non-negative integer")
        body = {"document": asdict(document), "expected_revision": expected_revision}
        def prepare():
            objects = self.objects()
            old = objects.get(document.object_id)
            if (old["revision"] if old else 0) != expected_revision:
                raise StoreError("STALE_VERSION", "Object changed since it was read")
            if old and old["document"]["kind"] != document.kind:
                raise StoreError("INVALID_OBJECT", "Changing an object's kind requires a new identity")
            if not old and len(objects) >= 256:
                raise StoreError("CONTEXT_TOO_LARGE", "This local context supports at most 256 objects")
            if self.sql.execute("SELECT 1 FROM artifact_heads WHERE artifact_id=?", (document.object_id,)).fetchone():
                raise StoreError("ID_CONFLICT", "Object and artifact identifiers must be distinct")
            for _, target in document.links:
                if target not in objects or target == document.object_id:
                    raise StoreError("UNKNOWN_REFERENCE", "Links must reference an existing different object")
            for source in document.source_ids:
                if source not in objects and not self.sql.execute("SELECT 1 FROM evidence_records WHERE evidence_id=?", (source,)).fetchone():
                    raise StoreError("UNKNOWN_REFERENCE", f"Unknown documentary source: {source}")
            semantic = document.semantic()
            sha = digest(canonical(semantic).encode())
            changed = old is None or old["sha256"] != sha
            candidate = {**objects, document.object_id: {"document": semantic}}
            for relation, target in document.links:
                if relation in DEPENDENCIES and document.object_id in self._closure([target], candidate):
                    raise StoreError("DEPENDENCY_CYCLE", "Dependency cycle rejected")
            return {"object_id": document.object_id, "revision": expected_revision + int(changed), "sha256": sha,
                    "semantic": semantic, "title": document.title, "changed": changed}
        def persist(seq, result):
            if result["changed"]:
                self.sql.execute("INSERT INTO object_revisions VALUES(?,?,?,?,?,?,?)",
                                 (document.object_id, result["revision"], canonical(result["semantic"]), result["sha256"],
                                  principal.actor_id, principal.role, seq))
            self.sql.execute("INSERT INTO object_heads VALUES(?,?,?) ON CONFLICT(object_id) DO UPDATE SET revision=excluded.revision,title=excluded.title",
                             (document.object_id, result["revision"], document.title))
            if result["changed"]:
                self.sql.execute("DELETE FROM review_flags WHERE object_id=?", (document.object_id,))
                objects = self.objects()
                for oid in objects:
                    if oid != document.object_id and document.object_id in self._closure([oid], objects):
                        self.sql.execute("INSERT INTO review_flags VALUES(?,?,?) ON CONFLICT(object_id,dependency_id) DO UPDATE SET event_seq=excluded.event_seq",
                                         (oid, document.object_id, seq))
        return self._mutate("OBJECT_UPDATED", body, principal, event_id, prepare, persist)

    def policy(self):
        row = self.sql.execute("SELECT revision,object_ids_json FROM dependency_policy").fetchone()
        return {"revision": row[0], "object_ids": json.loads(row[1])}

    def set_required(self, object_ids, principal, *, expected_revision: int, event_id: str):
        self._authorize(principal, {Role.HUMAN})
        ids = sorted(references(object_ids))
        def prepare():
            policy = self.policy()
            if type(expected_revision) is not int or expected_revision != policy["revision"]:
                raise StoreError("STALE_VERSION", "Mandatory dependency policy changed")
            self._closure(ids, self.objects())
            return {"revision": policy["revision"] + int(ids != policy["object_ids"]), "object_ids": ids}
        return self._mutate("DEPENDENCIES_SET", {"object_ids": ids, "expected_revision": expected_revision}, principal,
                            event_id, prepare, lambda seq, result: self.sql.execute("UPDATE dependency_policy SET revision=?,object_ids_json=? WHERE singleton=1",
                                                                                (result["revision"], canonical(ids))))

    def get(self, snapshot_id):
        self.store._guard()
        row = self.sql.execute("SELECT manifest_json,details_json FROM snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        if not row:
            raise StoreError("UNKNOWN_SNAPSHOT", "Unknown snapshot")
        return {"manifest": json.loads(row[0]), "details": json.loads(row[1])}

    def list(self):
        self.store._guard()
        return [json.loads(row[0]) for row in self.sql.execute("SELECT manifest_json FROM snapshots ORDER BY event_seq DESC LIMIT 100")]

    def capture(self, paths, object_ids, principal, *, event_id: str, note: str | None = None):
        self._authorize(principal, {Role.HUMAN, Role.KERNEL})
        selected = sorted(references(object_ids))
        if not isinstance(paths, dict) or len(paths) > MAX_FILES:
            raise StoreError("CAPTURE_TOO_LARGE", "At most 64 explicit artifact paths are allowed")
        for key in paths:
            identifier(key)
        if len(set(paths.values())) != len(paths):
            raise StoreError("DUPLICATE_REFERENCE", "A path cannot have two artifact identifiers")
        body = {"paths": paths, "object_ids": selected}
        if note is not None:
            if not isinstance(note, str) or not 1 <= len(note) <= 4000:
                raise StoreError("INVALID_NOTE", "Checkpoint note must contain 1..4000 characters")
            body["note"] = note
        prior = self._prior("SNAPSHOT_CAPTURED", body, principal, event_id)
        if prior:
            return self.get(prior["manifest"]["snapshot_id"])
        plan = self.store.plan()
        policy = self.policy()
        objects = self.objects()
        closure = self._closure([*selected, *policy["object_ids"]], objects)
        if set(paths) & set(objects):
            raise StoreError("ID_CONFLICT", "Object and artifact identifiers must be distinct")
        captured = {key: objects[key] for key in sorted(closure)}
        cut = self.sql.execute("SELECT coalesce(max(event_seq),0) FROM events").fetchone()[0]
        blobs, files, issues = {}, {}, []
        total = 0
        for key, path in sorted(paths.items()):
            data, stable = read_checked(self.store.workspace, path)
            total += len(data)
            if total > MAX_TOTAL:
                raise StoreError("CAPTURE_TOO_LARGE", "A capture exceeds 8 MiB")
            sha = digest(data)
            blobs[sha] = data
            old = self.sql.execute("SELECT revision,sha256,relative_path FROM artifact_heads WHERE artifact_id=?", (key,)).fetchone()
            revision = 1 if old is None else old[0] + int(old[1] != sha or old[2] != path)
            files[key] = {"path": path, "sha256": sha, "size": len(data), "revision": revision}
            if not stable:
                issues.append(f"{key} changed while it was being read.")
        self.store._fault("capture_after_first_pass")
        for key, file in files.items():
            try:
                data, stable = read_checked(self.store.workspace, file["path"])
                if not stable or digest(data) != file["sha256"]:
                    issues.append(f"{key} differs between the two reads.")
            except (OSError, StoreError):
                issues.append(f"{key} can no longer be read within the authorized scope.")
        def prepare():
            current = self.objects()
            if self.store.plan() != plan or self.policy() != policy or any(
                    key not in current or (current[key]["revision"], current[key]["sha256"]) != (item["revision"], item["sha256"])
                    for key, item in captured.items()):
                issues.append("The canonical context changed during the capture.")
            manifest = {"schema_version": "0.1", "project_id": plan.project_id, "cut_event_seq": cut,
                        "mission_revision": plan.mission_revision, "policy_revision": plan.policy_revision,
                        "plan_epoch": plan.epoch, "object_versions": [
                            {"object_id": key, "revision": item["revision"], "sha256": item["sha256"]} for key, item in captured.items()],
                        "artifact_manifest": [{"artifact_id": key, "sha256": file["sha256"]} for key, file in files.items()],
                        "stability": "UNSTABLE" if issues else "STABLE"}
            details = {"format_version": 1, "objects": captured, "files": files, "dependency_policy": policy,
                       "issues": issues, "capture_method": "two-pass-content-check"}
            if note is not None:
                details["agent_note"] = {"text": note, "status": "UNVERIFIED"}
            manifest["snapshot_id"] = "S-" + digest(canonical({"manifest": manifest, "details": details}).encode())
            manifest["created_at"] = self.store.clock.now().astimezone(timezone.utc).isoformat()
            validate_contract("snapshot", manifest)
            return {"manifest": manifest, "details": details}
        def persist(seq, result):
            sid = result["manifest"]["snapshot_id"]
            for sha, data in blobs.items():
                self.sql.execute("INSERT OR IGNORE INTO artifact_blobs VALUES(?,?,?)", (sha, data, len(data)))
            self.sql.execute("INSERT INTO snapshots VALUES(?,?,?,?)", (sid, canonical(result["manifest"]), canonical(result["details"]), seq))
            for key, file in files.items():
                self.sql.execute("INSERT INTO snapshot_artifacts VALUES(?,?,?,?,?)", (sid, key, file["sha256"], file["path"], file["revision"]))
                if result["manifest"]["stability"] == "STABLE":
                    self.sql.execute("INSERT INTO artifact_heads VALUES(?,?,?,?) ON CONFLICT(artifact_id) DO UPDATE SET revision=excluded.revision,sha256=excluded.sha256,relative_path=excluded.relative_path",
                                     (key, file["revision"], file["sha256"], file["path"]))
        receipt = self._mutate("SNAPSHOT_CAPTURED", body, principal, event_id, prepare, persist)
        row = self.sql.execute("SELECT snapshot_id FROM snapshots WHERE event_seq=?", (receipt.event_seq,)).fetchone()
        return self.get(row[0])

    def start_review(self, snapshot_id, review_id, principal, *, event_id):
        self._authorize(principal, {Role.DIRECTOR})
        identifier(review_id)
        if not principal.run_id:
            raise StoreError("UNAUTHORIZED", "A director review requires a trusted run identity")
        def prepare():
            self.get(snapshot_id)
            return {"review_id": review_id, "snapshot_id": snapshot_id}
        return self._mutate("REVIEW_STARTED", {"snapshot_id": snapshot_id, "review_id": review_id}, principal, event_id, prepare,
                            lambda seq, result: self.sql.execute("INSERT INTO review_sessions(review_id,snapshot_id,actor_id,run_id) VALUES(?,?,?,?)",
                                                                (review_id, snapshot_id, principal.actor_id, principal.run_id)))

    def _session(self, review_id, principal=None):
        row = self.sql.execute("SELECT * FROM review_sessions WHERE review_id=?", (review_id,)).fetchone()
        if not row:
            raise StoreError("UNKNOWN_REVIEW", "Unknown director review")
        if principal:
            self._authorize(principal, {Role.DIRECTOR})
            if (row["actor_id"], row["run_id"]) != (principal.actor_id, principal.run_id):
                raise StoreError("UNAUTHORIZED", "Review belongs to another director run")
        return row

    def artifact(self, snapshot_id, artifact_id):
        """Trusted inspection. Director proposal reviews must use logged read_context."""
        row = self.sql.execute("SELECT a.sha256,b.content FROM snapshot_artifacts a JOIN artifact_blobs b USING(sha256) WHERE snapshot_id=? AND artifact_id=?",
                               (snapshot_id, artifact_id)).fetchone()
        if not row:
            raise StoreError("UNKNOWN_REFERENCE", "Artifact is not in this snapshot")
        if digest(row[1]) != row[0]:
            raise StoreError("ARTIFACT_CORRUPT", "Immutable artifact fingerprint does not match")
        return row[1]

    def read_context(self, review_id, reference_id, principal, *, event_id):
        session = self._session(review_id, principal)
        snapshot = self.get(session["snapshot_id"])
        objects, files = snapshot["details"]["objects"], snapshot["details"]["files"]
        if reference_id in objects:
            kind, content = "OBJECT", objects[reference_id]
        elif reference_id in files:
            kind, content = "ARTIFACT", self.artifact(session["snapshot_id"], reference_id)
        else:
            raise StoreError("UNAUTHORIZED", "Reference is outside the captured context")
        def prepare():
            if self._session(review_id, principal)["sealed"]:
                raise StoreError("REVIEW_SEALED", "This review already submitted its proposal")
            return {"snapshot_id": session["snapshot_id"], "reference_id": reference_id, "kind": kind}
        self._mutate("CONTEXT_READ", {"review_id": review_id, "reference_id": reference_id}, principal, event_id, prepare,
                     lambda seq, result: self.sql.execute("INSERT OR IGNORE INTO served_reads VALUES(?,?,?,?)", (review_id, reference_id, kind, seq)))
        return content

    @staticmethod
    def check_read_set(proposal):
        references([item["object_id"] for item in proposal["read_set"]])

    def check_binding(self, review_id, proposal, principal):
        row = self._session(review_id, principal)
        if row["sealed"] or row["snapshot_id"] != proposal["basis_snapshot_id"]:
            raise StoreError("REVIEW_MISMATCH", "Proposal must use its own unsealed snapshot review")

    def record_evidence(self, evidence_id, snapshot_id, artifact_id, check_id, principal, evaluator, *, event_id):
        self._authorize(principal, {Role.VERIFIER})
        identifier(evidence_id)
        identifier(check_id)
        body = {"evidence_id": evidence_id, "snapshot_id": snapshot_id, "artifact_id": artifact_id, "check_id": check_id}
        prior = self._prior("EVIDENCE_RECORDED", body, principal, event_id)
        if prior:
            return prior
        snapshot = self.get(snapshot_id)
        if snapshot["manifest"]["stability"] != "STABLE":
            raise StoreError("UNSTABLE_SNAPSHOT", "Evidence requires a stable captured input")
        tested_bytes = self.artifact(snapshot_id, artifact_id)
        verdict = evaluator(tested_bytes)  # Deliberately outside a SQLite transaction.
        if verdict not in ("PASS", "FAIL", "INCONCLUSIVE"):
            raise StoreError("INVALID_VERDICT", "The trusted evaluator must return a supported verdict")
        result = {**body, "sha256": digest(tested_bytes), "verdict": verdict, "verifier": principal.actor_id}
        self._mutate("EVIDENCE_RECORDED", body, principal, event_id, lambda: result,
                     lambda seq, data: self.sql.execute("INSERT INTO evidence_records VALUES(?,?,?,?,?,?,?,?)",
                                                        (evidence_id, snapshot_id, artifact_id, result["sha256"], check_id, verdict, principal.actor_id, seq)))
        return result

    def _compare_references(self, snapshot, origins):
        captured, files = snapshot["details"]["objects"], snapshot["details"]["files"]
        current = self.objects()
        issues, dependencies = [], []
        def issue(code, message, reference=None):
            issues.append({"code": code, "message": message, "reference_id": reference})
        flagged = {row[0] for row in self.sql.execute("SELECT DISTINCT object_id FROM review_flags")}
        for rid, origin in sorted(origins.items()):
            item = captured.get(rid, files.get(rid))
            state, current_hash, current_revision = "CURRENT", None, None
            if item is None:
                state = "MISSING"
                issue("DEPENDENCY_NOT_CAPTURED", "A dependency is missing from the snapshot.", rid)
            elif rid in captured:
                now = current.get(rid)
                if now:
                    current_hash, current_revision = now["sha256"], now["revision"]
                if now is None or (current_revision, current_hash) != (item["revision"], item["sha256"]):
                    state = "CHANGED"
                    issue("OBJECT_CHANGED", "A premise was replaced after the capture.", rid)
                elif rid in flagged:
                    state = "REVIEW_REQUIRED"
                    issue("DEPENDENT_NEEDS_REVIEW", "This item depends on a modified premise: it needs review.", rid)
            else:
                head = self.sql.execute("SELECT revision,sha256,relative_path FROM artifact_heads WHERE artifact_id=?", (rid,)).fetchone()
                current_revision = head[0] if head else None
                if head is None or tuple(head) != (item["revision"], item["sha256"], item["path"]):
                    state = "CHANGED"
                    issue("ARTIFACT_BINDING_CHANGED", "The file identity now points to another version or path.", rid)
                try:
                    data, stable = read_checked(self.store.workspace, item["path"])
                    current_hash = digest(data)
                    if not stable or current_hash != item["sha256"]:
                        state = "CHANGED"
                        issue("ARTIFACT_CHANGED", "The current file differs from the captured content.", rid)
                except (OSError, StoreError):
                    state = "MISSING"
                    issue("ARTIFACT_UNAVAILABLE", "The file can no longer be read within the authorized scope.", rid)
            dependencies.append({"reference_id": rid, "origins": sorted(origin), "state": state,
                                 "expected_revision": item["revision"] if item else None, "current_revision": current_revision,
                                 "expected_sha256": item["sha256"] if item else None, "current_sha256": current_hash})
        return {"issues": issues, "dependencies": dependencies}

    def compare(self, snapshot_id):
        """Inspect every captured premise; this is not proposal admission."""
        snapshot = self.get(snapshot_id)
        details, manifest = snapshot["details"], snapshot["manifest"]
        origins = {rid: {"captured"} for rid in [*details["objects"], *details["files"]]}
        result = self._compare_references(snapshot, origins)
        if manifest["stability"] != "STABLE":
            result["issues"].append({"code": "UNSTABLE_SNAPSHOT", "message": "The capture was unstable.", "reference_id": None})
        plan = self.store.plan()
        if any(manifest[k] != v for k, v in (("mission_revision", plan.mission_revision), ("policy_revision", plan.policy_revision), ("plan_epoch", plan.epoch))) or self.policy() != details["dependency_policy"]:
            result["issues"].append({"code": "CONTEXT_VERSION_CHANGED", "message": "The framing of the capture (mission, policy or plan) changed.", "reference_id": None})
        return {**result, "eligible": not result["issues"], "stability": manifest["stability"],
                "snapshot_id": snapshot_id, "purpose": "CONTEXT_INSPECTION_NOT_AUTHORIZATION"}

    def validate(self, proposal, *, review_id=None):
        """Freshness is an observation at validation time, not a filesystem lease."""
        validate_contract("decision-proposal", proposal)
        self.check_read_set(proposal)
        issues, dependencies = [], []
        def issue(code, message, reference=None):
            issues.append({"code": code, "message": message, "reference_id": reference})
        try:
            snapshot = self.get(proposal["basis_snapshot_id"])
        except StoreError:
            return {"eligible": False, "stability": "UNKNOWN", "issues": [{"code": "UNKNOWN_SNAPSHOT", "message": "Snapshot not found.", "reference_id": None}], "dependencies": []}
        manifest, details = snapshot["manifest"], snapshot["details"]
        plan = self.store.plan()
        if manifest["stability"] != "STABLE":
            issue("UNSTABLE_SNAPSHOT", "The file changed while it was being captured.")
        for field, expected in (("project_id", plan.project_id), ("mission_revision", plan.mission_revision), ("policy_revision", plan.policy_revision), ("plan_epoch", plan.epoch)):
            proposal_field = "expected_plan_epoch" if field == "plan_epoch" else field
            if manifest[field] != expected or proposal[proposal_field] != expected:
                issue("STALE_VERSION", f"The {field} no longer matches the authorized context.")
        if proposal["basis_event_seq"] != manifest["cut_event_seq"]:
            issue("CUT_MISMATCH", "The journal cut does not match the snapshot.")
        if review_id is None:
            row = self.sql.execute("SELECT review_id FROM proposal_reviews WHERE project_id=? AND proposal_id=?", (plan.project_id, proposal["proposal_id"])).fetchone()
            review_id = row[0] if row else None
        served = []
        if review_id is None:
            issue("REVIEW_REQUIRED", "No read session is attached to this proposal.")
        else:
            session = self._session(review_id)
            if session["snapshot_id"] != manifest["snapshot_id"]:
                issue("REVIEW_MISMATCH", "The read session concerns another snapshot.")
            served = [row[0] for row in self.sql.execute("SELECT reference_id FROM served_reads WHERE review_id=?", (review_id,))]
        captured, files = details["objects"], details["files"]
        origins = {}
        def add(reference, origin):
            origins.setdefault(reference, set()).add(origin)
        for ref in proposal["read_set"]:
            rid = ref["object_id"]
            add(rid, "declared")
            item = captured.get(rid, files.get(rid))
            if item is None or ref["revision"] != item["revision"] or ref["sha256"] not in (None, item["sha256"]):
                issue("READ_SET_MISMATCH", "A declared read does not match the captured content.", rid)
        for rid in served:
            add(rid, "served")
        policy = self.policy()
        if policy != details["dependency_policy"]:
            issue("DEPENDENCY_POLICY_CHANGED", "The mandatory dependencies changed.")
        for rid in {*policy["object_ids"], *details["dependency_policy"]["object_ids"], *files}:
            add(rid, "mandatory")
        for rid in list(origins):
            if rid in captured:
                for linked in self._closure([rid], captured):
                    add(linked, "dependency")
        compared = self._compare_references(snapshot, origins)
        issues.extend(compared["issues"])
        dependencies.extend(compared["dependencies"])
        for evidence_id in proposal["evidence_ids"]:
            row = self.sql.execute("SELECT artifact_id,sha256 FROM evidence_records WHERE evidence_id=?", (evidence_id,)).fetchone()
            if row is None or row[0] not in files or row[1] != files[row[0]]["sha256"]:
                issue("EVIDENCE_UNBOUND", "The evidence is not bound to this snapshot's content.", evidence_id)
        return {"eligible": not issues, "stability": manifest["stability"], "issues": issues, "dependencies": dependencies,
                "snapshot_id": manifest["snapshot_id"], "cut_event_seq": manifest["cut_event_seq"],
                "checked_at": getattr(self.store, "clock", None).now().isoformat() if hasattr(self.store, "clock") else None}
