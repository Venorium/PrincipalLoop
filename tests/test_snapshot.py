from dataclasses import replace
import json
import os
from pathlib import Path

import pytest

from principalloop.domain.types import Action, Command, Principal, Role, Status
from principalloop.snapshot import Document
from principalloop.snapshot.files import MAX_FILE, digest, read_checked
from principalloop.store import Store, StoreError
from test_store_transitions import READY, activate_ready, create


@pytest.fixture
def captured(storage_case):
    store, proposal = create(storage_case)
    try:
        yield storage_case, store, proposal
    finally:
        store.close()


def test_t05_replaced_premise_refuses_activation_and_can_be_marked_stale(captured):
    c, store, proposal = captured
    store.snapshots.put_object(Document("H-1", "HYPOTHESIS", "Premise", "The original assumption is contradicted."),
                               c["human"], expected_revision=1, event_id="DOC-2")
    assessment = store.snapshots.validate(proposal)
    assert not assessment["eligible"]
    assert "OBJECT_CHANGED" in {issue["code"] for issue in assessment["issues"]}
    with pytest.raises(StoreError, match="STALE_CONTEXT"):
        store.apply(proposal["proposal_id"], Command(Action.PUBLISH, 1, decision_id="D-1", worker_run_id="RUN-1"),
                    c["kernel"], checks=READY, event_id="PUBLISH")
    store.apply(proposal["proposal_id"], Command(Action.MARK_STALE, 1, reason="Premise H-1 changed"), c["kernel"], event_id="STALE")
    assert store.decision(proposal["proposal_id"]).status == Status.STALE and store.plan().epoch == 0


def test_t06_unrelated_events_and_descriptive_renaming_preserve_freshness(captured):
    c, store, proposal = captured
    store.record_event(c["event"], c["worker"])
    store.snapshots.put_object(Document("UNRELATED", "OBSERVATION", "Other task", "A different scope changed."),
                               c["worker"], expected_revision=0, event_id="OTHER-DOC")
    store.snapshots.put_object(Document("H-1", "HYPOTHESIS", "A clearer display title", "A bounded premise"),
                               c["human"], expected_revision=1, event_id="RENAME")
    assert store.snapshots.validate(proposal)["eligible"]
    assert len(store.snapshots.history("H-1")) == 1
    assert store.snapshots.get(proposal["basis_snapshot_id"])["details"]["objects"]["H-1"]["title"] == "Premise"


def test_rebinding_artifact_identity_invalidates_original_even_with_same_bytes(captured):
    c, store, proposal = captured
    (c["workspace"] / "other.txt").write_bytes(b"captured input")
    store.snapshots.capture({"F-1": "other.txt"}, ["H-1"], c["human"], event_id="REBIND")
    result = store.snapshots.validate(proposal)
    assert not result["eligible"]
    assert "ARTIFACT_BINDING_CHANGED" in {i["code"] for i in result["issues"]}


@pytest.mark.parametrize("change", ["file", "object"])
def test_real_freshness_is_rechecked_between_begin_and_activation(captured, change):
    c, store, proposal = captured
    command = activate_ready(store, c, proposal)
    if change == "file":
        (c["workspace"] / "input.txt").write_bytes(b"new input")
    else:
        store.snapshots.put_object(Document("H-1", "HYPOTHESIS", "Changed", "Changed premise"), c["human"], expected_revision=1, event_id="NEW")
    before = store.plan()
    with pytest.raises(StoreError, match="STALE_CONTEXT"):
        store.apply(proposal["proposal_id"], command, c["kernel"], event_id="ACTIVATE", checks=READY)
    assert store.plan() == before and store.decision(proposal["proposal_id"]).status == Status.ACTIVATING


def test_t19_capture_detects_interpass_change_and_preserves_first_bytes(captured):
    c, store, proposal = captured
    def mutation(phase):
        if phase == "capture_after_first_pass":
            (c["workspace"] / "input.txt").write_bytes(b"changed during capture")
    store._fault = mutation
    result = store.snapshots.capture({"F-1": "input.txt"}, ["H-1"], c["human"], event_id="UNSTABLE")
    assert result["manifest"]["stability"] == "UNSTABLE"
    sid = result["manifest"]["snapshot_id"]
    assert store.snapshots.artifact(sid, "F-1") == b"captured input"
    verifier = Principal("verifier", Role.VERIFIER, c["mission"]["project_id"])
    with pytest.raises(StoreError, match="UNSTABLE_SNAPSHOT"):
        store.snapshots.record_evidence("E-2", sid, "F-1", "check-v1", verifier, lambda _: "PASS", event_id="NO-PROOF")


def test_evidence_checks_immutable_bytes_outside_transaction_and_retry_never_reruns(captured):
    c, store, proposal = captured
    sid = proposal["basis_snapshot_id"]
    (c["workspace"] / "input.txt").write_bytes(b"new working tree contents")
    calls = []
    def evaluator(content):
        assert not store._connection.in_transaction
        calls.append(content)
        return "PASS"
    verifier = Principal("independent-verifier", Role.VERIFIER, c["mission"]["project_id"])
    first = store.snapshots.record_evidence("E-2", sid, "F-1", "bytes-check-v1", verifier, evaluator, event_id="PROOF-2")
    second = store.snapshots.record_evidence("E-2", sid, "F-1", "bytes-check-v1", verifier, evaluator, event_id="PROOF-2")
    assert first == second and calls == [b"captured input"]
    assert first["sha256"] == digest(calls[0]) != digest((c["workspace"] / "input.txt").read_bytes())
    with pytest.raises(StoreError, match="UNAUTHORIZED"):
        store.snapshots.record_evidence("E-3", sid, "F-1", "check-v1", c["director"], evaluator, event_id="BAD-PROOF")


def unbound_review(c, store, *, required=False):
    store.snapshots.put_object(Document("H-2", "HYPOTHESIS", "Second premise", "An undeclared dependency."), c["human"], expected_revision=0, event_id="H2")
    if required:
        store.snapshots.set_required(["H-2"], c["human"], expected_revision=1, event_id="REQUIRED")
    snapshot = store.snapshots.capture({"F-1": "input.txt"}, ["H-1", "H-2"], c["human"], event_id="CAPTURE-2")
    store.snapshots.start_review(snapshot["manifest"]["snapshot_id"], "REVIEW-2", c["director"], event_id="REVIEW-2")
    return snapshot


@pytest.mark.parametrize("coverage", ["served", "mandatory", "omitted"])
def test_x01_served_or_mandatory_dependency_cannot_be_omitted_but_unknown_semantics_can(captured, coverage):
    c, store, proposal = captured
    snapshot = unbound_review(c, store, required=coverage == "mandatory")
    candidate = {**proposal, "proposal_id": "P-NEW", "basis_snapshot_id": snapshot["manifest"]["snapshot_id"],
                 "basis_event_seq": snapshot["manifest"]["cut_event_seq"]}
    if coverage == "served":
        store.snapshots.read_context("REVIEW-2", "H-2", c["director"], event_id="READ-H2")
    store.register_proposal(candidate, c["director"], review_id="REVIEW-2", event_id="P-NEW")
    store.snapshots.put_object(Document("H-2", "HYPOTHESIS", "Second premise", "The premise was replaced."), c["human"], expected_revision=1, event_id="H2-CHANGE")
    result = store.snapshots.validate(candidate)
    assert result["eligible"] is (coverage == "omitted")
    if coverage != "omitted":
        dep = next(item for item in result["dependencies"] if item["reference_id"] == "H-2")
        assert coverage in dep["origins"] and dep["state"] == "CHANGED"


def test_read_context_is_scoped_to_snapshot_run_and_logged_before_return(captured):
    c, store, _ = captured
    snapshot = unbound_review(c, store)
    with pytest.raises(StoreError, match="UNAUTHORIZED"):
        store.snapshots.read_context("REVIEW-2", "H-1", replace(c["director"], run_id="different"), event_id="READ")
    with pytest.raises(StoreError, match="UNAUTHORIZED"):
        store.snapshots.read_context("REVIEW-2", "outside", c["director"], event_id="READ")
    value = store.snapshots.read_context("REVIEW-2", "F-1", c["director"], event_id="READ")
    assert value == b"captured input"
    assert store.journal()[-1]["operation"] == "CONTEXT_READ"
    with pytest.raises(StoreError, match="REVIEW_SEALED"):
        store.snapshots.read_context("REVIEW-1", "H-1", c["director"], event_id="SEALED")


def test_graph_changes_mark_dependents_for_review_without_declaring_them_false(captured):
    c, store, _ = captured
    store.snapshots.put_object(Document("CHILD", "HYPOTHESIS", "Consequence", "May remain true.", (("depends_on", "H-1"),)),
                               c["human"], expected_revision=0, event_id="CHILD")
    with pytest.raises(StoreError, match="DEPENDENCY_CYCLE"):
        store.snapshots.put_object(Document("H-1", "HYPOTHESIS", "Cycle", "Wrong cycle", (("depends_on", "CHILD"),)), c["human"], expected_revision=1, event_id="CYCLE")
    store.snapshots.put_object(Document("H-1", "HYPOTHESIS", "Premise", "Updated."), c["human"], expected_revision=1, event_id="CHANGE")
    assert store._connection.execute("SELECT object_id FROM review_flags").fetchone()[0] == "CHILD"
    assert store.snapshots.objects()["CHILD"]["document"]["content"] == "May remain true."
    assert len(store.snapshots.history("H-1")) == 2


def test_duplicate_read_id_unknown_evidence_and_untrusted_policy_are_refused(captured):
    c, store, proposal = captured
    bad = {**proposal, "read_set": [*proposal["read_set"], {**proposal["read_set"][0], "revision": 999}]}
    with pytest.raises(StoreError, match="DUPLICATE_REFERENCE"):
        store.register_proposal(bad, c["director"], event_id="DUPLICATE")
    unknown = {**proposal, "evidence_ids": ["E-NOT-REAL"]}
    assert not store.snapshots.validate(unknown)["eligible"]
    with pytest.raises(StoreError, match="UNAUTHORIZED"):
        store.snapshots.set_required(["H-1"], c["director"], expected_revision=1, event_id="POLICY")
    with pytest.raises(StoreError, match="UNAUTHORIZED"):
        store.snapshots.put_object(Document("RULE", "CONSTRAINT", "Rule", "Change the human objective"), c["director"], expected_revision=0, event_id="RULE")


@pytest.mark.parametrize("path", ["../outside.txt", ".env", ".git/config", ".codex/auth.json", "C:/secret.txt", "/absolute", "input.txt:secret", "./input.txt"])
def test_capture_path_boundaries(captured, path):
    c, store, _ = captured
    with pytest.raises(StoreError, match="PATH_DENIED"):
        store.snapshots.capture({"PRIVATE": path}, ["H-1"], c["human"], event_id="PRIVATE")


def test_file_size_hardlinks_and_normal_windows_metadata(captured):
    c, store, _ = captured
    path = c["workspace"] / "big.txt"
    path.write_bytes(b"x" * (MAX_FILE + 1))
    with pytest.raises(StoreError, match="CAPTURE_TOO_LARGE"):
        store.snapshots.capture({"BIG": "big.txt"}, [], c["human"], event_id="BIG")
    for _ in range(3):
        assert read_checked(c["workspace"], "input.txt")[1]
    os.link(c["workspace"] / "input.txt", c["workspace"] / "alias.txt")
    with pytest.raises(StoreError, match="PATH_DENIED"):
        store.snapshots.capture({"LINK": "alias.txt"}, [], c["human"], event_id="LINK")


def test_capture_retry_returns_original_even_if_worktree_is_gone(captured):
    c, store, proposal = captured
    (c["workspace"] / "input.txt").unlink()
    retry = store.snapshots.capture({"F-1": "input.txt"}, ["H-1"], c["human"], event_id="CAPTURE-1")
    assert retry["manifest"]["snapshot_id"] == proposal["basis_snapshot_id"]
    assert store.snapshots.artifact(proposal["basis_snapshot_id"], "F-1") == b"captured input"


@pytest.mark.parametrize("phase", ["after_event", "after_view", "after_outbox", "before_commit"])
def test_capture_rollback_has_no_orphan_blob_or_manifest(captured, phase):
    c, store, _ = captured
    before = (len(store.snapshots.list()), store._connection.execute("SELECT count(*) FROM artifact_blobs").fetchone()[0], store.status()["event_count"])
    (c["workspace"] / "input.txt").write_bytes(b"distinct blob")
    def fail(at):
        if at == phase:
            raise OSError("injected write failure")
    store._fault = fail
    with pytest.raises(OSError):
        store.snapshots.capture({"F-1": "input.txt"}, [], c["human"], event_id="FAIL")
    after = (len(store.snapshots.list()), store._connection.execute("SELECT count(*) FROM artifact_blobs").fetchone()[0], store.status()["event_count"])
    assert after == before
