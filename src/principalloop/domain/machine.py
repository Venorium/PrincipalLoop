"""Pure state machine: returns a new joint state, never a commit or an external effect."""

from dataclasses import replace
from datetime import datetime
from types import MappingProxyType

from .contracts import validate_contract
from .types import (
    Action, Checks, Clock, Command, Decision, DomainError, Kind, Mode,
    Plan, PRE_ACTIVE, Principal, Role, Status, TERMINAL, Trajectory, Transition,
)


# RECEIVE exceptions and pre-ACTIVE outcomes are explicit, never implicit.
TRANSITIONS = MappingProxyType({
    Action.REQUEST_APPROVAL: (frozenset({Status.PROPOSED}), Status.WAITING_APPROVAL),
    Action.PUBLISH: (frozenset({Status.PROPOSED}), Status.PUBLISHED),
    Action.APPROVE: (frozenset({Status.WAITING_APPROVAL}), Status.PUBLISHED),
    Action.REJECT_POLICY: (frozenset({Status.PROPOSED}), Status.REJECTED_POLICY),
    Action.ACCEPT: (frozenset({Status.PUBLISHED}), Status.ACCEPTED),
    Action.DEFER: (frozenset({Status.PUBLISHED}), Status.DEFERRED),
    Action.CONTEST: (frozenset({Status.PUBLISHED}), Status.CONTESTED),
    Action.REPUBLISH: (frozenset({Status.DEFERRED, Status.CONTESTED}), Status.PUBLISHED),
    Action.BEGIN_ACTIVATION: (frozenset({Status.ACCEPTED}), Status.ACTIVATING),
    Action.ACTIVATE: (frozenset({Status.ACTIVATING}), Status.ACTIVE),
    Action.SUBMIT_RESULT: (frozenset({Status.ACTIVE}), Status.RESULT_SUBMITTED),
    Action.ANSWER_ESCALATION: (frozenset({Status.PUBLISHED}), Status.RESULT_SUBMITTED),
    Action.VERIFY: (frozenset({Status.RESULT_SUBMITTED}), Status.VERIFIED),
    Action.FAIL: (frozenset({Status.RESULT_SUBMITTED}), Status.FAILED),
    Action.MARK_STALE: (PRE_ACTIVE, Status.STALE),
    Action.EXPIRE: (PRE_ACTIVE, Status.EXPIRED),
    Action.CANCEL: (frozenset(set(Status) - TERMINAL), Status.CANCELLED),
})

ROLES = MappingProxyType({
    Action.REQUEST_APPROVAL: frozenset({Role.KERNEL}),
    Action.PUBLISH: frozenset({Role.KERNEL}),
    Action.APPROVE: frozenset({Role.HUMAN}),
    Action.REJECT_POLICY: frozenset({Role.KERNEL}),
    Action.RECEIVE: frozenset({Role.EXECUTOR, Role.HUMAN}),
    Action.ACCEPT: frozenset({Role.EXECUTOR}),
    Action.DEFER: frozenset({Role.EXECUTOR}),
    Action.CONTEST: frozenset({Role.EXECUTOR}),
    Action.REPUBLISH: frozenset({Role.KERNEL}),
    Action.BEGIN_ACTIVATION: frozenset({Role.KERNEL}),
    Action.ACTIVATE: frozenset({Role.KERNEL}),
    Action.SUBMIT_RESULT: frozenset({Role.EXECUTOR}),
    Action.ANSWER_ESCALATION: frozenset({Role.HUMAN}),
    Action.VERIFY: frozenset({Role.VERIFIER}),
    Action.FAIL: frozenset({Role.VERIFIER}),
    Action.MARK_STALE: frozenset({Role.EXECUTOR, Role.KERNEL}),
    Action.EXPIRE: frozenset({Role.KERNEL}),
    Action.CANCEL: frozenset({Role.HUMAN, Role.KERNEL}),
})


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise DomainError(code, detail)


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))


def propose(payload: str | bytes | dict, principal: Principal) -> Decision:
    document = validate_contract("decision-proposal", payload)
    _require(principal.role == Role.DIRECTOR, "UNAUTHORIZED", "Only the director submits a proposal")
    _require(principal.project_id == document["project_id"], "UNAUTHORIZED", "Wrong project")
    return Decision(
        proposal_id=document["proposal_id"], project_id=document["project_id"],
        kind=Kind(document["kind"]), scope=tuple(document["scope"]),
        mission_revision=int(document["mission_revision"]), policy_revision=int(document["policy_revision"]),
        expected_plan_epoch=int(document["expected_plan_epoch"]), snapshot_id=document["basis_snapshot_id"],
        expires_at=timestamp(document["activation"]["expires_at"]),
        requests_human_approval=document["authority_requested"] == "HUMAN_APPROVAL",
    )


def _fresh(decision: Decision, plan: Plan, checks: Checks, now: datetime):
    _require(plan.mode != Mode.SHADOW, "UNAUTHORIZED", "SHADOW cannot advance an executable decision")
    _require(now < decision.expires_at, "EXPIRED", "Activation deadline reached")
    _require((decision.mission_revision, decision.policy_revision, decision.expected_plan_epoch) ==
             (plan.mission_revision, plan.policy_revision, plan.epoch), "STALE_VERSION", "Mission, policy or plan changed")
    _require(checks.dependencies_current and checks.snapshot_stable, "STALE_VERSION", "Dependencies or snapshot not attested")
    _require(checks.policy_allowed, "UNAUTHORIZED", "Policy does not authorize this action")
    _require(checks.budget_reserved, "BUDGET_EXCEEDED", "No budget reservation attested")
    _require(set(decision.scope) <= dict(plan.scopes).keys(), "UNAUTHORIZED", "Scope not in the mission")


def _safe(checks: Checks):
    _require(checks.safepoint_ready, "UNSAFE_BOUNDARY", "Safe point not attested")
    _require(checks.effects_reconciled, "UNKNOWN_EFFECT", "Effects not reconciled")


def advance(decision: Decision, plan: Plan, command: Command, principal: Principal,
            clock: Clock, checks: Checks = Checks()) -> Transition:
    """Transport and attestations are trusted inputs, not OS authentication."""
    now = clock.now()
    _require(isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None,
             "INVALID_INPUT", "Clock must return a timezone-aware datetime")
    _require(principal.project_id == plan.project_id == decision.project_id, "UNAUTHORIZED", "Wrong project")
    _require(isinstance(command.action, Action) and principal.role in ROLES[command.action], "UNAUTHORIZED", "Role cannot perform action")

    if principal.role == Role.EXECUTOR:
        _require(principal.run_id is not None and principal.run_id == decision.worker_run_id,
                 "UNAUTHORIZED", "Worker is not the assigned recipient")
    if command.action == Action.RECEIVE:
        _require(decision.decision_id is not None, "INVALID_TRANSITION", "Unpublished decision")
        recipient = Role.HUMAN if decision.kind == Kind.ESCALATE else Role.EXECUTOR
        _require(principal.role == recipient, "UNAUTHORIZED", "Wrong receipt recipient")
        return Transition(decision, plan, "RECEIVED")

    _require(command.expected_revision == decision.revision, "STALE_VERSION", "Decision revision changed")
    origins, target = TRANSITIONS[command.action]
    _require(decision.status in origins, "INVALID_TRANSITION", f"{decision.status} -> {command.action}")
    action = command.action
    changes = {"status": target, "revision": decision.revision + 1}
    updated_plan = plan

    if decision.kind == Kind.ESCALATE:
        _require(action not in {Action.ACCEPT, Action.DEFER, Action.CONTEST, Action.BEGIN_ACTIVATION, Action.ACTIVATE, Action.SUBMIT_RESULT},
                 "INVALID_TRANSITION", "Escalation uses the human arbitration path")
    else:
        _require(action != Action.ANSWER_ESCALATION, "INVALID_TRANSITION", "Not an escalation")

    if action in {Action.DEFER, Action.CONTEST, Action.ANSWER_ESCALATION}:
        _require(now < decision.expires_at, "EXPIRED", "Response deadline reached")

    if action in {Action.PUBLISH, Action.APPROVE, Action.REPUBLISH, Action.ACCEPT, Action.BEGIN_ACTIVATION, Action.ACTIVATE}:
        _fresh(decision, plan, checks, now)
        if decision.kind != Kind.ESCALATE:
            needs_approval = decision.requests_human_approval or checks.requires_human_approval
            _require(not needs_approval or action == Action.APPROVE or decision.approved_by is not None,
                     "APPROVAL_REQUIRED", "Current policy requires approval of this precise intention")

    if action in {Action.PUBLISH, Action.APPROVE}:
        _require(plan.mode != Mode.SHADOW, "UNAUTHORIZED", "SHADOW cannot publish executable decisions")
        if decision.kind != Kind.ESCALATE:
            _require(bool(command.worker_run_id), "INVALID_INPUT", "Assigned worker required")
        _require(bool(command.decision_id), "INVALID_INPUT", "Kernel-assigned decision ID required")
        changes.update(decision_id=command.decision_id, worker_run_id=command.worker_run_id)
        if action == Action.APPROVE:
            changes["approved_by"] = principal.actor_id

    if action in {Action.CONTEST, Action.MARK_STALE, Action.CANCEL, Action.REJECT_POLICY, Action.FAIL, Action.ANSWER_ESCALATION}:
        _require(bool(command.reason.strip()), "INVALID_INPUT", "A factual reason is required")

    if action == Action.DEFER:
        deadline = command.defer_until
        _require(deadline is not None and deadline.tzinfo is not None and deadline.utcoffset() is not None,
                 "INVALID_INPUT", "DEFER requires a timezone-aware deadline")
        _require(now < deadline <= decision.expires_at and bool(command.resume_trigger and command.resume_trigger.strip()),
                 "INVALID_INPUT", "DEFER requires a bounded deadline and trigger")
        changes.update(defer_until=deadline, resume_trigger=command.resume_trigger)

    if action == Action.REPUBLISH:
        if decision.status == Status.DEFERRED:
            _require(checks.defer_trigger_fired or (decision.defer_until is not None and now >= decision.defer_until),
                     "UNSAFE_BOUNDARY", "Deferred event not reached")
        else:
            _require(checks.objection_resolved, "UNRESOLVED_OBJECTION", "No evidence or arbitration resolving objection")
        changes.update(defer_until=None, resume_trigger=None)

    if action == Action.BEGIN_ACTIVATION:
        _require(plan.mode != Mode.SHADOW, "UNAUTHORIZED", "SHADOW cannot activate")
        _require(plan.owner is None, "CONFLICTING_DECISION", "Another transition owns the plan")
        updated_plan = replace(plan, owner=decision.proposal_id)

    if action == Action.ACTIVATE:
        _require(plan.mode != Mode.SHADOW, "UNAUTHORIZED", "SHADOW cannot activate")
        _require(plan.owner == decision.proposal_id, "CONFLICTING_DECISION", "Activation ownership missing")
        _safe(checks)
        scopes = dict(plan.scopes)
        _require(set(decision.scope) <= scopes.keys(), "UNAUTHORIZED", "Scope not in the mission")
        for scope in decision.scope:
            current = scopes[scope]
            if decision.kind == Kind.RESUME:
                _require(current == Trajectory.PAUSED, "UNSAFE_BOUNDARY", "Only paused scopes can resume")
                scopes[scope] = Trajectory.RUNNING
            elif decision.kind == Kind.PAUSE:
                _require(current == Trajectory.RUNNING, "UNSAFE_BOUNDARY", "Only running scopes can pause")
                scopes[scope] = Trajectory.PAUSED
            elif decision.kind == Kind.STOP_BRANCH:
                _require(current != Trajectory.STOPPED, "UNSAFE_BOUNDARY", "Scope already stopped")
                scopes[scope] = Trajectory.STOPPED
            else:
                _require(current == Trajectory.RUNNING, "UNSAFE_BOUNDARY", "Scope is not running")
        updated_plan = replace(plan, epoch=plan.epoch + 1, scopes=tuple(scopes.items()))
        changes["activated_epoch"] = updated_plan.epoch

    if action in {Action.SUBMIT_RESULT, Action.ANSWER_ESCALATION}:
        _require(bool(command.result_id) and bool(command.evidence_ids), "INVALID_INPUT", "Result and evidence references required")
        if action == Action.SUBMIT_RESULT:
            _require(decision.activated_epoch == plan.epoch and plan.owner == decision.proposal_id,
                     "STALE_VERSION", "Result belongs to an earlier plan")
        changes.update(result_id=command.result_id, evidence_ids=command.evidence_ids)

    if action == Action.VERIFY:
        _require(checks.result_verified, "UNVERIFIED_RESULT", "Independent verification not attested")
    if action == Action.EXPIRE:
        _require(now >= decision.expires_at, "INVALID_TRANSITION", "Activation deadline not reached")
    if target in TERMINAL and plan.owner == decision.proposal_id:
        if decision.status in {Status.ACTIVATING, Status.ACTIVE, Status.RESULT_SUBMITTED}:
            _safe(checks)
        updated_plan = replace(plan, owner=None)

    return Transition(replace(decision, **changes), updated_plan, action.value)


def respond(decision: Decision, plan: Plan, payload: str | bytes | dict,
            principal: Principal, clock: Clock, checks: Checks = Checks()) -> Transition:
    document = validate_contract("decision-response", payload)
    _require(document["project_id"] == decision.project_id and document["decision_id"] == decision.decision_id,
             "INVALID_INPUT", "Response targets another decision")
    _require(document["worker_run_id"] == principal.run_id, "UNAUTHORIZED", "Claimed worker differs from authenticated run")
    _require(document["observed_plan_epoch"] == plan.epoch, "STALE_VERSION", "Observed plan changed")
    action = Action.MARK_STALE if document["response"] == "STALE" else Action(document["response"])
    return advance(decision, plan, Command(
        action, int(document["expected_decision_revision"]), reason=document["reason"],
        defer_until=timestamp(document["defer_until"]) if document["defer_until"] else None,
        resume_trigger=document["resume_trigger"],
    ), principal, clock, checks)


def submit_result(decision: Decision, plan: Plan, payload: str | bytes | dict,
                  principal: Principal, clock: Clock, expected_revision: int,
                  checks: Checks = Checks()) -> Transition:
    """A claimed success or failure gives no independent verdict."""
    document = validate_contract("result", payload)
    _require(document["project_id"] == decision.project_id and document["decision_id"] == decision.decision_id,
             "INVALID_INPUT", "Result targets another decision")
    _require(document["worker_run_id"] == principal.run_id, "UNAUTHORIZED", "Claimed worker differs from authenticated run")
    _require(document["plan_epoch"] == decision.activated_epoch == plan.epoch,
             "STALE_VERSION", "Result belongs to an earlier plan; retain separately for revalidation")
    return advance(decision, plan, Command(
        Action.SUBMIT_RESULT, expected_revision, result_id=document["result_id"],
        evidence_ids=tuple(document["evidence_ids"]),
    ), principal, clock, checks)
