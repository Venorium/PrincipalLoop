from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from hypothesis import given, settings, strategies as st
import pytest

from principalloop.domain.machine import ROLES, TRANSITIONS, advance, propose, respond, submit_result
from principalloop.domain.types import (
    Action, Checks, Command, Decision, DomainError, FixedClock, Kind, Mode, Plan,
    Principal, Role, Status, TERMINAL, Trajectory, Utility,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
CLOCK = FixedClock(NOW)
READY = Checks(policy_allowed=True, dependencies_current=True, snapshot_stable=True,
               budget_reserved=True, requires_human_approval=False, safepoint_ready=True,
               effects_reconciled=True, result_verified=True)


def actor(role, project="demo", run="RUN-1"):
    return Principal(f"actor-{role}", role, project, run if role == Role.EXECUTOR else None)


def initial(kind=Kind.INVESTIGATE, epoch=0):
    return Decision("P-1", "demo", kind, ("service",), 1, 1, epoch, "S-1", NOW + timedelta(minutes=10), False)


def plan(mode=Mode.COOPERATIVE):
    return Plan("demo", 1, 1, 0, (("service", Trajectory.RUNNING), ("other", Trajectory.RUNNING)), mode)


def step(decision, state, action, *, principal=None, checks=READY, clock=CLOCK, **kwargs):
    if principal is None:
        principal = actor(sorted(ROLES[action], key=lambda role: role.value)[0])
    fields = dict(reason="Observed test evidence", decision_id="D-1", worker_run_id="RUN-1",
                  result_id="R-1", evidence_ids=("E-1",))
    fields.update(kwargs)
    transition = advance(decision, state, Command(action, decision.revision, **fields), principal, clock, checks)
    return transition.decision, transition.plan


def published(kind=Kind.INVESTIGATE):
    return step(initial(kind), plan(), Action.PUBLISH)


def active(kind=Kind.INVESTIGATE):
    decision, state = published(kind)
    for action in (Action.ACCEPT, Action.BEGIN_ACTIVATION, Action.ACTIVATE):
        decision, state = step(decision, state, action)
    return decision, state


def finish(decision, state):
    decision, state = step(decision, state, Action.SUBMIT_RESULT)
    return step(decision, state, Action.VERIFY)


def test_accept_receipt_and_active_are_distinct_and_inputs_stay_immutable():
    decision, state = published()
    before = deepcopy((decision, state))
    receipt, unchanged = step(decision, state, Action.RECEIVE, principal=actor(Role.EXECUTOR))
    assert receipt is decision and unchanged is state
    accepted, unchanged = step(decision, state, Action.ACCEPT)
    assert accepted.status == Status.ACCEPTED and unchanged.epoch == 0
    assert unchanged.owner is None
    activating, owned = step(accepted, unchanged, Action.BEGIN_ACTIVATION)
    assert owned.epoch == 0 and owned.owner == decision.proposal_id
    activated, next_plan = step(activating, owned, Action.ACTIVATE)
    assert activated.status == Status.ACTIVE and activated.activated_epoch == next_plan.epoch == 1
    assert (decision, state) == before
    with pytest.raises(FrozenInstanceError):
        activated.status = Status.PUBLISHED
    with pytest.raises(DomainError, match="INVALID_TRANSITION"):
        step(activated, next_plan, Action.ACTIVATE)


def test_result_requires_independent_verification_and_utility_is_separate():
    decision, state = active()
    decision, state = step(decision, state, Action.SUBMIT_RESULT)
    assert decision.status == Status.RESULT_SUBMITTED
    with pytest.raises(DomainError, match="UNAUTHORIZED"):
        step(decision, state, Action.VERIFY, principal=actor(Role.EXECUTOR))
    with pytest.raises(DomainError, match="UNVERIFIED_RESULT"):
        step(decision, state, Action.VERIFY, checks=replace(READY, result_verified=False))
    decision, state = step(decision, state, Action.VERIFY)
    assert decision.status == Status.VERIFIED and state.owner is None
    assert decision.utility == Utility.INCONCLUSIVE and state.epoch == 1


def test_pause_finishes_then_resume_can_obtain_ownership():
    decision, state = finish(*active(Kind.PAUSE))
    assert dict(state.scopes)["service"] == Trajectory.PAUSED and state.owner is None
    resume = replace(initial(Kind.RESUME, epoch=1), proposal_id="P-2")
    for action in (Action.PUBLISH, Action.ACCEPT, Action.BEGIN_ACTIVATION, Action.ACTIVATE):
        resume, state = step(resume, state, action, decision_id="D-2")
    resume, state = finish(resume, state)
    assert dict(state.scopes)["service"] == Trajectory.RUNNING
    assert state.epoch == 2 and state.owner is None


def test_stop_branch_preserves_other_scope_and_cannot_resume_stopped_scope():
    decision, state = finish(*active(Kind.STOP_BRANCH))
    assert dict(state.scopes) == {"service":Trajectory.STOPPED, "other":Trajectory.RUNNING}
    resume = replace(initial(Kind.RESUME, epoch=1), proposal_id="P-2")
    for action in (Action.PUBLISH, Action.ACCEPT, Action.BEGIN_ACTIVATION):
        resume, state = step(resume, state, action)
    with pytest.raises(DomainError, match="UNSAFE_BOUNDARY"):
        step(resume, state, Action.ACTIVATE)


def test_escalation_uses_human_path_without_epoch_or_ownership():
    decision, state = published(Kind.ESCALATE)
    with pytest.raises(DomainError, match="INVALID_TRANSITION"):
        step(decision, state, Action.ACCEPT)
    for action in (Action.ANSWER_ESCALATION, Action.VERIFY):
        decision, state = step(decision, state, action)
        assert state.epoch == 0 and state.owner is None
    assert decision.status == Status.VERIFIED and decision.activated_epoch is None


def test_human_approval_is_required_and_bound_to_fresh_policy():
    decision = replace(initial(), requests_human_approval=True)
    with pytest.raises(DomainError, match="APPROVAL_REQUIRED"):
        step(decision, plan(), Action.PUBLISH)
    decision, state = step(decision, plan(), Action.REQUEST_APPROVAL)
    with pytest.raises(DomainError, match="UNAUTHORIZED"):
        step(decision, state, Action.APPROVE, principal=actor(Role.DIRECTOR))
    with pytest.raises(DomainError, match="STALE_VERSION"):
        step(decision, replace(state, policy_revision=2), Action.APPROVE)
    decision, state = step(decision, state, Action.APPROVE)
    assert decision.status == Status.PUBLISHED and state.epoch == 0


@pytest.mark.parametrize("field,code", [
    ("policy_allowed", "UNAUTHORIZED"), ("dependencies_current", "STALE_VERSION"),
    ("snapshot_stable", "STALE_VERSION"), ("budget_reserved", "BUDGET_EXCEEDED"),
    ("safepoint_ready", "UNSAFE_BOUNDARY"), ("effects_reconciled", "UNKNOWN_EFFECT"),
])
def test_activation_fails_closed_when_any_guard_is_missing(field, code):
    decision, state = published()
    for action in (Action.ACCEPT, Action.BEGIN_ACTIVATION):
        decision, state = step(decision, state, action)
    with pytest.raises(DomainError, match=code):
        step(decision, state, Action.ACTIVATE, checks=replace(READY, **{field:False}))
    assert decision.status == Status.ACTIVATING and state.epoch == 0


def test_default_checks_authorize_nothing_and_shadow_cannot_publish():
    with pytest.raises(DomainError):
        step(initial(), plan(), Action.PUBLISH, checks=Checks())
    with pytest.raises(DomainError, match="UNAUTHORIZED"):
        step(initial(), plan(Mode.SHADOW), Action.PUBLISH)


def test_revision_worker_project_and_concurrent_ownership_are_checked():
    decision, state = published()
    for principal in (actor(Role.DIRECTOR), actor(Role.EXECUTOR, run="RUN-OLD"), actor(Role.EXECUTOR, project="other")):
        with pytest.raises(DomainError, match="UNAUTHORIZED"):
            step(decision, state, Action.ACCEPT, principal=principal)
    with pytest.raises(DomainError, match="STALE_VERSION"):
        advance(decision, state, Command(Action.ACCEPT, 1), actor(Role.EXECUTOR), CLOCK, READY)
    decision, state = step(decision, state, Action.ACCEPT)
    with pytest.raises(DomainError, match="CONFLICTING_DECISION"):
        step(decision, replace(state, owner="P-other"), Action.BEGIN_ACTIVATION)


def test_expiration_boundary_and_active_work_do_not_share_timeout_semantics():
    decision, state = published()
    at_deadline = FixedClock(decision.expires_at)
    with pytest.raises(DomainError, match="EXPIRED"):
        step(decision, state, Action.ACCEPT, clock=at_deadline)
    expired, state = step(decision, state, Action.EXPIRE, clock=at_deadline)
    assert expired.status == Status.EXPIRED and state.epoch == 0
    decision, state = active()
    with pytest.raises(DomainError, match="INVALID_TRANSITION"):
        step(decision, state, Action.EXPIRE, clock=at_deadline)
    decision, state = step(decision, state, Action.SUBMIT_RESULT, clock=at_deadline)
    assert decision.status == Status.RESULT_SUBMITTED


def test_defer_and_contest_require_bounded_resolution():
    decision, state = published()
    with pytest.raises(DomainError, match="INVALID_INPUT"):
        step(decision, state, Action.DEFER)
    deferred, state = step(decision, state, Action.DEFER, defer_until=NOW+timedelta(minutes=1), resume_trigger="task-ended")
    with pytest.raises(DomainError, match="UNSAFE_BOUNDARY"):
        step(deferred, state, Action.REPUBLISH)
    republished, state = step(deferred, state, Action.REPUBLISH, clock=FixedClock(NOW+timedelta(minutes=1)))
    contested, state = step(republished, state, Action.CONTEST)
    with pytest.raises(DomainError, match="UNRESOLVED_OBJECTION"):
        step(contested, state, Action.REPUBLISH)
    decision, state = step(contested, state, Action.REPUBLISH, checks=replace(READY, objection_resolved=True))
    assert decision.status == Status.PUBLISHED and decision.proposal_id == deferred.proposal_id


def test_cancel_requires_reconciliation_and_keeps_already_applied_pause():
    decision, state = active(Kind.PAUSE)
    with pytest.raises(DomainError, match="UNKNOWN_EFFECT"):
        step(decision, state, Action.CANCEL, checks=replace(READY, effects_reconciled=False))
    cancelled, state = step(decision, state, Action.CANCEL)
    assert cancelled.status == Status.CANCELLED and state.epoch == 1
    assert dict(state.scopes)["service"] == Trajectory.PAUSED and state.owner is None


def test_all_forbidden_edges_and_terminals_remain_closed():
    for source in Status:
        decision = replace(initial(), status=source, decision_id="D-1", worker_run_id="RUN-1")
        for action, (origins, _) in TRANSITIONS.items():
            if source not in origins:
                with pytest.raises(DomainError, match="INVALID_TRANSITION"):
                    step(decision, plan(), action)
    for terminal in TERMINAL:
        decision = replace(initial(), status=terminal, decision_id="D-1", worker_run_id="RUN-1")
        receipt, state = step(decision, plan(), Action.RECEIVE, principal=actor(Role.EXECUTOR))
        assert receipt is decision and state.epoch == 0


def test_wire_proposal_and_response_do_not_assign_authority():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "examples/decision-proposal.json").read_text(encoding="utf-8"))
    payload.update(project_id="demo", mission_revision=1, policy_revision=1, expected_plan_epoch=0, scope=["service"])
    payload["activation"]["expires_at"] = "2026-10-04T13:00:00Z"
    with pytest.raises(DomainError, match="UNAUTHORIZED"):
        propose(payload, actor(Role.EXECUTOR))
    decision = propose(payload, actor(Role.DIRECTOR))
    decision, state = step(decision, plan(), Action.PUBLISH)
    response = json.loads((root / "examples/decision-response.json").read_text(encoding="utf-8"))
    response.update(project_id="demo", decision_id="D-1", worker_run_id="RUN-1", expected_decision_revision=decision.revision,
                    observed_plan_epoch=0, response="ACCEPT", resume_trigger=None, defer_until=None)
    accepted = respond(decision, state, response, actor(Role.EXECUTOR), CLOCK, READY)
    assert accepted.decision.status == Status.ACCEPTED and accepted.plan.epoch == 0
    response["worker_run_id"] = "fake"
    with pytest.raises(DomainError, match="UNAUTHORIZED"):
        respond(decision, state, response, actor(Role.EXECUTOR), CLOCK, READY)


@pytest.mark.parametrize("action", [Action.DEFER, Action.CONTEST])
def test_late_responses_are_refused_even_without_activation(action):
    decision, state = published()
    with pytest.raises(DomainError, match="EXPIRED"):
        step(decision, state, action, clock=FixedClock(decision.expires_at),
             defer_until=decision.expires_at, resume_trigger="ready")


def test_return_to_shadow_prevents_republication_and_acceptance():
    decision, state = published()
    with pytest.raises(DomainError, match="UNAUTHORIZED"):
        step(decision, replace(state, mode=Mode.SHADOW), Action.ACCEPT)
    decision, state = step(decision, state, Action.CONTEST)
    with pytest.raises(DomainError, match="UNAUTHORIZED"):
        step(decision, replace(state, mode=Mode.SHADOW), Action.REPUBLISH,
             checks=replace(READY, objection_resolved=True))


@pytest.mark.parametrize("factory", [
    lambda: replace(READY, policy_allowed="false"),
    lambda: replace(initial(), scope=["service"]),
    lambda: replace(initial(), mission_revision=True),
    lambda: replace(initial(), expires_at=NOW.replace(tzinfo=None)),
    lambda: replace(plan(), scopes=(("service", Trajectory.RUNNING), ("service", Trajectory.PAUSED))),
    lambda: Command(Action.ACCEPT, 1, evidence_ids=["E-1"]),
    lambda: Principal("attacker", "KERNEL", "demo"),
])
def test_internal_values_reject_mutability_ambiguous_types_and_invalid_identity(factory):
    with pytest.raises(DomainError, match="INVALID_INPUT"):
        factory()


def test_multi_scope_refusal_does_not_partially_resume():
    state = replace(plan(), scopes=(("service", Trajectory.PAUSED), ("other", Trajectory.RUNNING)))
    decision = replace(initial(Kind.RESUME), scope=("service", "other"))
    for action in (Action.PUBLISH, Action.ACCEPT, Action.BEGIN_ACTIVATION):
        decision, state = step(decision, state, action)
    with pytest.raises(DomainError, match="UNSAFE_BOUNDARY"):
        step(decision, state, Action.ACTIVATE)
    assert dict(state.scopes)["service"] == Trajectory.PAUSED and state.epoch == 0


@pytest.mark.parametrize("kind,before,after", [
    (Kind.INVESTIGATE, Trajectory.RUNNING, Trajectory.RUNNING),
    (Kind.REPRIORITIZE, Trajectory.RUNNING, Trajectory.RUNNING),
    (Kind.REFRAME, Trajectory.RUNNING, Trajectory.RUNNING),
    (Kind.PAUSE, Trajectory.RUNNING, Trajectory.PAUSED),
    (Kind.RESUME, Trajectory.PAUSED, Trajectory.RUNNING),
    (Kind.STOP_BRANCH, Trajectory.RUNNING, Trajectory.STOPPED),
])
def test_each_executable_kind_completes_with_one_epoch(kind, before, after):
    decision = initial(kind)
    state = replace(plan(), scopes=(("service", before), ("other", Trajectory.RUNNING)))
    for action in (Action.PUBLISH, Action.ACCEPT, Action.BEGIN_ACTIVATION, Action.ACTIVATE):
        decision, state = step(decision, state, action)
    decision, state = finish(decision, state)
    assert decision.status == Status.VERIFIED and state.epoch == 1 and state.owner is None
    assert dict(state.scopes) == {"service":after, "other":Trajectory.RUNNING}


def test_policy_can_require_approval_even_when_director_requests_autonomy():
    with pytest.raises(DomainError, match="APPROVAL_REQUIRED"):
        step(initial(), plan(), Action.PUBLISH, checks=replace(READY, requires_human_approval=True))


@pytest.mark.parametrize("field", ["mission_revision", "policy_revision", "epoch"])
def test_final_activation_rechecks_versions_after_acceptance(field):
    decision, state = published()
    for action in (Action.ACCEPT, Action.BEGIN_ACTIVATION):
        decision, state = step(decision, state, action)
    changed = replace(state, **{field:getattr(state, field)+1})
    with pytest.raises(DomainError, match="STALE_VERSION"):
        step(decision, changed, Action.ACTIVATE)
    assert decision.status == Status.ACTIVATING and decision.activated_epoch is None


def test_wire_result_checks_generation_recipient_and_never_self_verifies():
    decision, state = active()
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "examples/contracts/result.json").read_text(encoding="utf-8"))
    payload.update(project_id="demo", decision_id="D-1", plan_epoch=1, worker_run_id="RUN-1")
    for field, value, error in [("plan_epoch", 0, "STALE_VERSION"), ("decision_id", "other", "INVALID_INPUT"),
                                ("worker_run_id", "other", "UNAUTHORIZED")]:
        with pytest.raises(DomainError, match=error):
            submit_result(decision, state, dict(payload, **{field:value}), actor(Role.EXECUTOR), CLOCK, decision.revision)
    submitted = submit_result(decision, state, payload, actor(Role.EXECUTOR), CLOCK, decision.revision)
    assert submitted.decision.status == Status.RESULT_SUBMITTED
    assert submitted.decision.utility == Utility.INCONCLUSIVE and submitted.plan is state
    failed, released = step(submitted.decision, state, Action.FAIL)
    assert failed.status == Status.FAILED and released.owner is None


def test_receipt_with_older_revision_has_no_business_effect():
    decision, state = finish(*active())
    transition = advance(decision, state, Command(Action.RECEIVE, 1), actor(Role.EXECUTOR), CLOCK)
    assert transition.decision is decision and transition.plan is state


def test_approval_rejection_and_early_expiration():
    rejected, unchanged = step(initial(), plan(), Action.REJECT_POLICY)
    assert rejected.status == Status.REJECTED_POLICY and unchanged.epoch == 0
    decision, state = step(initial(), plan(), Action.REQUEST_APPROVAL)
    cancelled, state = step(decision, state, Action.CANCEL, principal=actor(Role.HUMAN))
    assert cancelled.status == Status.CANCELLED and state.epoch == 0
    with pytest.raises(DomainError, match="INVALID_TRANSITION"):
        step(initial(), plan(), Action.EXPIRE)


def test_new_approval_requirement_at_activation_cannot_be_bypassed():
    decision, state = published()
    for action in (Action.ACCEPT, Action.BEGIN_ACTIVATION):
        decision, state = step(decision, state, action)
    with pytest.raises(DomainError, match="APPROVAL_REQUIRED"):
        step(decision, state, Action.ACTIVATE, checks=replace(READY, requires_human_approval=True))


def test_authenticated_approval_remains_bound_to_the_same_intention():
    decision = replace(initial(), requests_human_approval=True)
    state = plan()
    for action in (Action.REQUEST_APPROVAL, Action.APPROVE, Action.ACCEPT, Action.BEGIN_ACTIVATION, Action.ACTIVATE):
        decision, state = step(decision, state, action, checks=replace(READY, requires_human_approval=True))
    assert decision.approved_by == actor(Role.HUMAN).actor_id
    assert decision.status == Status.ACTIVE and state.epoch == 1


@settings(max_examples=100, derandomize=True, deadline=None)
@given(st.lists(st.sampled_from(list(Action)), min_size=1, max_size=60))
def test_arbitrary_action_sequences_preserve_epoch_terminal_and_revision_invariants(actions):
    decision, state = initial(), plan()
    for action in actions:
        old_decision, old_state = decision, state
        try:
            decision, state = step(decision, state, action, defer_until=NOW+timedelta(minutes=1), resume_trigger="ready")
        except DomainError:
            assert (decision, state) == (old_decision, old_state)
            continue
        assert state.epoch - old_state.epoch == (1 if action == Action.ACTIVATE else 0)
        assert decision.revision - old_decision.revision == (0 if action == Action.RECEIVE else 1)
        if old_decision.status in TERMINAL:
            assert decision == old_decision and state == old_state
        assert decision.utility == Utility.INCONCLUSIVE
