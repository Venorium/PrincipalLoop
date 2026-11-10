from contextlib import closing
import json
from pathlib import Path
import sqlite3

import pytest

from principalloop.domain.types import Action, Checks, Command, DomainError, Mode, Status, Principal, Role
from principalloop.snapshot import Document
from principalloop.store import Store, StoreError


READY = Checks(policy_allowed=True, dependencies_current=True, snapshot_stable=True,
               budget_reserved=True, requires_human_approval=False, safepoint_ready=True,
               effects_reconciled=True)


def create(case):
    store = Store(case["database"], workspace=case["workspace"], clock=case["clock"])
    store.initialize(case["mission"], case["human"], mode=Mode.COOPERATIVE)
    root = Path(__file__).resolve().parents[1]
    proposal = json.loads((root / "examples/decision-proposal.json").read_text(encoding="utf-8"))
    proposal.update(project_id=case["mission"]["project_id"], scope=["service"], expected_plan_epoch=0)
    store.snapshots.put_object(Document("H-1", "HYPOTHESIS", "Premise", "A bounded premise"), case["human"], expected_revision=0, event_id="DOC-1")
    (case["workspace"] / "input.txt").write_bytes(b"captured input")
    snapshot = store.snapshots.capture({"F-1": "input.txt"}, ["H-1"], case["human"], event_id="CAPTURE-1")
    manifest = snapshot["manifest"]
    case["director"] = Principal("director", Role.DIRECTOR, case["mission"]["project_id"], "DIRECTOR-1")
    store.snapshots.start_review(manifest["snapshot_id"], "REVIEW-1", case["director"], event_id="REVIEW-START")
    verifier = Principal("verifier", Role.VERIFIER, case["mission"]["project_id"])
    store.snapshots.record_evidence("E-087", manifest["snapshot_id"], "F-1", "fixture-check-v1", verifier,
                                   lambda content: "PASS" if content == b"captured input" else "FAIL", event_id="PROOF-1")
    proposal.update(basis_snapshot_id=manifest["snapshot_id"], basis_event_seq=manifest["cut_event_seq"], read_set=manifest["object_versions"])
    store.register_proposal(proposal, case["director"], event_id="P-1", review_id="REVIEW-1")
    return store, proposal


def activate_ready(store, case, proposal):
    pid = proposal["proposal_id"]
    store.apply(pid, Command(Action.PUBLISH, 1, decision_id="D-1", worker_run_id="RUN-1"),
                case["kernel"], event_id="C-1", checks=READY)
    store.apply(pid, Command(Action.ACCEPT, 2), case["worker"], event_id="C-2", checks=READY)
    store.apply(pid, Command(Action.BEGIN_ACTIVATION, 3), case["kernel"], event_id="C-3", checks=READY)
    return Command(Action.ACTIVATE, 4)


def test_persisted_activation_retries_do_not_advance_epoch_twice(storage_case):
    c = storage_case
    store, proposal = create(c)
    pid = proposal["proposal_id"]
    with store:
        command = activate_ready(store, c, proposal)
        receipt = store.apply(pid, command, c["kernel"], event_id="C-4", checks=READY)
        assert store.decision(pid).status == Status.ACTIVE
        assert store.decision(pid).activated_epoch == store.plan().epoch == 1
        assert store.proposal(pid) == proposal
        before = store.status()
        event = store.journal(after=receipt.event_seq - 1)[0]
        assert event["outcome"]["checks"]["safepoint_ready"] is True
    with Store(c["database"], workspace=c["workspace"], clock=c["clock"]) as store:
        # Recheck/clock context can change after restart; retry acknowledges the old commit.
        retry = store.apply(pid, command, c["kernel"], event_id="C-4")
        assert retry.duplicate and retry.event_seq == receipt.event_seq
        assert store.status() == before
        with pytest.raises(StoreError, match="STALE_CONTEXT"):
            store.apply(pid, command, c["kernel"], event_id="C-5", checks=READY)
        with closing(sqlite3.connect(c["database"], autocommit=True)) as sql:
            assert sql.execute("SELECT count(*) FROM activations").fetchone()[0] == 1
            with pytest.raises(sqlite3.IntegrityError):
                sql.execute("INSERT INTO activations SELECT * FROM activations")
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                sql.execute("UPDATE decisions SET proposal_json='{}'")


@pytest.mark.parametrize("phase", ["after_event", "after_view", "after_outbox", "before_commit"])
def test_failed_activation_rolls_back_decision_plan_journal_and_outbox(storage_case, phase):
    c = storage_case
    store, proposal = create(c)
    with store:
        command = activate_ready(store, c, proposal)
        pid = proposal["proposal_id"]
        before = (store.decision(pid), store.plan(), store.journal(), store.outbox())
        def fail(at):
            if at == phase:
                raise OSError("Injected failure")
        store._fault = fail
        with pytest.raises(OSError):
            store.apply(pid, command, c["kernel"], event_id="C-4", checks=READY)
        assert (store.decision(pid), store.plan(), store.journal(), store.outbox()) == before
        with closing(sqlite3.connect(c["database"])) as sql:
            assert sql.execute("SELECT count(*) FROM activations").fetchone()[0] == 0


def test_stale_revision_missing_attestation_and_duplicate_proposal_fail_closed(storage_case):
    c = storage_case
    store, proposal = create(c)
    with store:
        pid = proposal["proposal_id"]
        before = store.status()
        with pytest.raises(DomainError):
            store.apply(pid, Command(Action.PUBLISH, 1, decision_id="D-1", worker_run_id="RUN-1"),
                        c["kernel"], event_id="C-1")
        with pytest.raises(DomainError):
            store.apply(pid, Command(Action.PUBLISH, 999), c["kernel"], event_id="C-1", checks=READY)
        with pytest.raises(StoreError, match="CONSTRAINT_CONFLICT"):
            store.register_proposal(proposal, c["director"], event_id="OTHER")
        assert store.status() == before
        assert store.register_proposal(proposal, c["director"], event_id="P-1", review_id="REVIEW-1").duplicate


@pytest.mark.parametrize("mutation", ["unknown-version", "missing-field"])
def test_corrupted_stored_domain_state_is_not_reinterpreted(storage_case, mutation):
    c = storage_case
    store, proposal = create(c)
    with store:
        with closing(sqlite3.connect(c["database"], autocommit=True)) as sql:
            state = json.loads(sql.execute("SELECT state_json FROM decisions").fetchone()[0])
            if mutation == "unknown-version":
                state["storage_version"] = 999
            else:
                del state["value"]["status"]
            sql.execute("UPDATE decisions SET state_json=?", (json.dumps(state),))
        with pytest.raises(StoreError, match="STATE_INVALID"):
            store.decision(proposal["proposal_id"])
