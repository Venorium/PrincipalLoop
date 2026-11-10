"""Immutable internal values. Principal is supplied by the authenticated transport, never by payloads."""

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class Role(StrEnum):
    HUMAN = "HUMAN"
    EXECUTOR = "EXECUTOR"
    DIRECTOR = "DIRECTOR"
    KERNEL = "KERNEL"
    VERIFIER = "VERIFIER"


class Mode(StrEnum):
    SHADOW = "SHADOW"
    COOPERATIVE = "COOPERATIVE"
    ENFORCED = "ENFORCED"


class Status(StrEnum):
    PROPOSED = "PROPOSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    REJECTED_POLICY = "REJECTED_POLICY"
    PUBLISHED = "PUBLISHED"
    ACCEPTED = "ACCEPTED"
    DEFERRED = "DEFERRED"
    CONTESTED = "CONTESTED"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    ACTIVATING = "ACTIVATING"
    ACTIVE = "ACTIVE"
    RESULT_SUBMITTED = "RESULT_SUBMITTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL = frozenset({Status.REJECTED_POLICY, Status.STALE, Status.EXPIRED, Status.VERIFIED, Status.FAILED, Status.CANCELLED})
PRE_ACTIVE = frozenset({Status.PROPOSED, Status.WAITING_APPROVAL, Status.PUBLISHED, Status.ACCEPTED, Status.DEFERRED, Status.CONTESTED, Status.ACTIVATING})


class Kind(StrEnum):
    INVESTIGATE = "INVESTIGATE"
    REPRIORITIZE = "REPRIORITIZE"
    REFRAME = "REFRAME"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    STOP_BRANCH = "STOP_BRANCH"
    ESCALATE = "ESCALATE"


class Trajectory(StrEnum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


class Utility(StrEnum):
    BENEFICIAL = "BENEFICIAL"
    HARMFUL = "HARMFUL"
    NO_MEASURABLE_EFFECT = "NO_MEASURABLE_EFFECT"
    INCONCLUSIVE = "INCONCLUSIVE"


class Action(StrEnum):
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    PUBLISH = "PUBLISH"
    APPROVE = "APPROVE"
    REJECT_POLICY = "REJECT_POLICY"
    RECEIVE = "RECEIVE"
    ACCEPT = "ACCEPT"
    DEFER = "DEFER"
    CONTEST = "CONTEST"
    REPUBLISH = "REPUBLISH"
    BEGIN_ACTIVATION = "BEGIN_ACTIVATION"
    ACTIVATE = "ACTIVATE"
    SUBMIT_RESULT = "SUBMIT_RESULT"
    ANSWER_ESCALATION = "ANSWER_ESCALATION"
    VERIFY = "VERIFY"
    FAIL = "FAIL"
    MARK_STALE = "MARK_STALE"
    EXPIRE = "EXPIRE"
    CANCEL = "CANCEL"


class Clock(Protocol):
    def now(self) -> datetime: ...


def _valid(condition, detail):
    if not condition:
        raise DomainError("INVALID_INPUT", detail)


def _text(value, name, optional=False):
    if optional and value is None:
        return
    _valid(isinstance(value, str) and bool(value.strip()), f"{name} must be nonblank text")


def _count(value, name, minimum=0):
    _valid(type(value) is int and value >= minimum, f"{name} must be an integer >= {minimum}")


def _aware(value, name):
    _valid(isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None,
           f"{name} must be a timezone-aware datetime")


def _refs(value, name, minimum=0):
    _valid(type(value) is tuple and len(value) >= minimum, f"{name} must be an immutable tuple")
    for item in value:
        _text(item, name)
    _valid(len(value) == len(set(value)), f"{name} contains duplicates")


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def __post_init__(self):
        _aware(self.instant, "instant")

    def now(self) -> datetime:
        return self.instant


@dataclass(frozen=True)
class Principal:
    actor_id: str
    role: Role
    project_id: str
    run_id: str | None = None

    def __post_init__(self):
        _text(self.actor_id, "actor_id")
        _text(self.project_id, "project_id")
        _text(self.run_id, "run_id", optional=True)
        _valid(isinstance(self.role, Role), "role must come from trusted typed context")
        _valid(self.role != Role.EXECUTOR or self.run_id is not None, "Executor requires authenticated run")


@dataclass(frozen=True)
class Plan:
    project_id: str
    mission_revision: int
    policy_revision: int
    epoch: int
    scopes: tuple[tuple[str, Trajectory], ...]
    mode: Mode = Mode.SHADOW
    owner: str | None = None

    def __post_init__(self):
        _text(self.project_id, "project_id")
        _text(self.owner, "owner", optional=True)
        _count(self.mission_revision, "mission_revision", 1)
        _count(self.policy_revision, "policy_revision", 1)
        _count(self.epoch, "epoch")
        _valid(isinstance(self.mode, Mode), "mode must be typed")
        _valid(type(self.scopes) is tuple and bool(self.scopes), "scopes must be a nonempty immutable tuple")
        names = []
        for item in self.scopes:
            _valid(type(item) is tuple and len(item) == 2, "scope entry must be an immutable pair")
            name, trajectory = item
            _text(name, "scope")
            _valid(isinstance(trajectory, Trajectory), "trajectory must be typed")
            names.append(name)
        _valid(len(names) == len(set(names)), "scope identifiers must be unique")


@dataclass(frozen=True)
class Decision:
    proposal_id: str
    project_id: str
    kind: Kind
    scope: tuple[str, ...]
    mission_revision: int
    policy_revision: int
    expected_plan_epoch: int
    snapshot_id: str
    expires_at: datetime
    requests_human_approval: bool
    status: Status = Status.PROPOSED
    revision: int = 1
    approved_by: str | None = None
    decision_id: str | None = None
    worker_run_id: str | None = None
    defer_until: datetime | None = None
    resume_trigger: str | None = None
    utility: Utility = Utility.INCONCLUSIVE
    activated_epoch: int | None = None
    result_id: str | None = None
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ("proposal_id", "project_id", "snapshot_id"):
            _text(getattr(self, name), name)
        for name in ("decision_id", "worker_run_id", "resume_trigger", "result_id", "approved_by"):
            _text(getattr(self, name), name, optional=True)
        for name in ("mission_revision", "policy_revision", "revision"):
            _count(getattr(self, name), name, 1)
        _count(self.expected_plan_epoch, "expected_plan_epoch")
        if self.activated_epoch is not None:
            _count(self.activated_epoch, "activated_epoch", 1)
        _refs(self.scope, "scope", 1)
        _refs(self.evidence_ids, "evidence_ids")
        _aware(self.expires_at, "expires_at")
        if self.defer_until is not None:
            _aware(self.defer_until, "defer_until")
        _valid(isinstance(self.kind, Kind) and isinstance(self.status, Status) and isinstance(self.utility, Utility),
               "Decision enums must be typed")
        _valid(type(self.requests_human_approval) is bool, "Approval request must be boolean")


@dataclass(frozen=True)
class Checks:
    """Facts attested by the kernel, never deserialized from model output."""
    policy_allowed: bool = False
    dependencies_current: bool = False
    snapshot_stable: bool = False
    budget_reserved: bool = False
    requires_human_approval: bool = True
    safepoint_ready: bool = False
    effects_reconciled: bool = False
    defer_trigger_fired: bool = False
    objection_resolved: bool = False
    result_verified: bool = False

    def __post_init__(self):
        _valid(all(type(getattr(self, field.name)) is bool for field in fields(self)), "Attestations must be actual booleans")


@dataclass(frozen=True)
class Command:
    action: Action
    expected_revision: int
    reason: str = ""
    decision_id: str | None = None
    worker_run_id: str | None = None
    defer_until: datetime | None = None
    resume_trigger: str | None = None
    result_id: str | None = None
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self):
        _valid(isinstance(self.action, Action), "Action must be typed")
        _count(self.expected_revision, "expected_revision", 1)
        _valid(isinstance(self.reason, str), "reason must be text")
        for name in ("decision_id", "worker_run_id", "resume_trigger", "result_id"):
            _text(getattr(self, name), name, optional=True)
        _refs(self.evidence_ids, "evidence_ids")
        if self.defer_until is not None:
            _aware(self.defer_until, "defer_until")


@dataclass(frozen=True)
class Transition:
    decision: Decision
    plan: Plan
    event: str


class DomainError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")
