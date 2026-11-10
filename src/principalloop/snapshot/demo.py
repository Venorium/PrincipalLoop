"""Eight synthetic cases executed by the kernel, without a model or user state (English or French text)."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from ..domain.types import FixedClock, Principal, Role
from ..store import Store
from .i18n import TEXT
from .types import Document


CASES = (("initial", True), ("noise", True), ("premise", False), ("file", False),
         ("unstable", False), ("served", False), ("mandatory", False), ("omitted", True))

# Displayed texts only; identifiers, expectations and the kernel's behavior do not depend on the language.
TEXTS = {
    "fr": {
        "initial": ("Tout est cohérent", "Le point de départ",
                    "Les prémisses lues et le fichier capturé sont inchangés. Le contexte reste utilisable pour examiner la proposition."),
        "noise": ("Un événement sans impact", "Savoir ne pas interrompre",
                  "Une autre tâche progresse. Le journal avance, mais aucune dépendance de la proposition n'a changé."),
        "premise": ("Une hypothèse remplacée", "Réexaminer les prémisses",
                    "L'hypothèse d'idempotence a été remplacée. La proposition fondée sur sa première révision doit être réexaminée."),
        "file": ("Le code a changé", "Suivre le contenu, pas le nom",
                 "Le fichier porte toujours le même nom. Son contenu diffère pourtant de celui capturé et contrôlé."),
        "unstable": ("Une capture instable", "Refuser une lecture incohérente",
                     "Le fichier a été modifié entre les deux lectures de capture. Les octets sont conservés, avec un statut instable explicite."),
        "served": ("Une lecture non déclarée", "Recouper les lectures servies",
                   "Le directeur a lu une seconde hypothèse puis l'a omise de sa proposition. Sa lecture enregistrée permet de détecter le changement."),
        "mandatory": ("Une dépendance impérative", "Respecter le périmètre humain",
                      "Une dépendance imposée par l'opérateur a changé. L'absence de cette référence dans la proposition ne la soustrait pas au contrôle."),
        "omitted": ("La limite à connaître", "Ce qui n'a jamais été observé",
                    "Une dépendance pertinente n'a été ni déclarée, ni servie, ni imposée. Le contrôle ne la découvre pas : un contexte admissible n'est pas une preuve de complétude."),
        "H-1": ("Une requête répétée, une seule commande", "Une nouvelle tentative conserve la même commande."),
        "H-2": ("Une clé transmise sans altération", "Le fournisseur conserve la clé de requête."),
        "revised": ("Une prémisse révisée", "La nouvelle observation contredit la prémisse précédente."),
        "source": "# Illustration : cette déclaration ne prouve pas l'idempotence.\n",
        "event": "La documentation d'un autre composant avance.",
    },
    "en": {
        "initial": ("Everything is consistent", "The starting point",
                    "The premises read and the captured file are unchanged. The context still supports reviewing the proposal."),
        "noise": ("An unrelated event", "Knowing when not to interrupt",
                  "Another task moves forward. The journal advances, but none of the proposal's dependencies changed."),
        "premise": ("A replaced hypothesis", "Re-examine the premises",
                    "The idempotency hypothesis was replaced. A proposal built on its first revision must be reviewed again."),
        "file": ("The code changed", "Track content, not names",
                 "The file keeps the same name, yet its content differs from what was captured and checked."),
        "unstable": ("An unstable capture", "Refuse an inconsistent read",
                     "The file changed between the two capture reads. The bytes are kept, with an explicit unstable status."),
        "served": ("An undeclared read", "Cross-check served reads",
                   "The director read a second hypothesis, then left it out of its proposal. The recorded read still reveals the change."),
        "mandatory": ("A mandatory dependency", "Respect the human scope",
                      "A dependency imposed by the operator changed. Leaving it out of the proposal does not exempt it from the check."),
        "omitted": ("The limit to know", "What was never observed",
                    "A relevant dependency was neither declared, served nor imposed. The check cannot find it: admissible context is not proof of completeness."),
        "H-1": ("A repeated request, a single order", "A retry keeps the same order."),
        "H-2": ("A key passed through unchanged", "The provider keeps the request key."),
        "revised": ("A revised premise", "The new observation contradicts the previous premise."),
        "source": "# Illustration: this declaration does not prove idempotency.\n",
        "event": "Documentation for another component moves forward.",
    },
}


def proposal_for(manifest):
    return {"schema_version": "0.1", "proposal_id": "P-DEMO", "project_id": manifest["project_id"],
            "mission_revision": manifest["mission_revision"], "policy_revision": manifest["policy_revision"],
            "basis_snapshot_id": manifest["snapshot_id"], "basis_event_seq": manifest["cut_event_seq"],
            "expected_plan_epoch": manifest["plan_epoch"], "kind": "INVESTIGATE", "scope": ["service"],
            "read_set": [item for item in manifest["object_versions"] if item["object_id"] == "H-1"],
            "evidence_ids": ["E-1"],
            "rationale": {"observation": "Un risque de doublon est rapporté.", "interpretation": "L'idempotence reste à éprouver.",
                          "why_change_now": "La suite dépend de cette hypothèse.", "why_not_continue": "Une vérification bornée pourrait éviter une reprise.",
                          "expected_benefit": "Clarifier le comportement de répétition.", "uncertainties": ["La cause peut être ailleurs."],
                          "would_be_refuted_by": "Un résultat indépendant sur le contenu pertinent."},
            "proposed_action": {"objective": "Examiner l'hypothèse sans modifier la mission.", "scope_delta": "SAME_SCOPE",
                                "parent_goal_id": "G-1", "suggested_next_steps": ["Vérifier les versions et les preuves."],
                                "stop_criteria": ["Contexte établi ou limite explicitée."]},
            "activation": {"boundary": "NEXT_SAFEPOINT", "expires_at": "2026-10-04T12:00:00Z"},
            "budget_request": {"additional_tokens": 0, "max_wall_seconds": 60, "max_tool_calls": 0},
            "verification": {"method": "EXISTING_TEST", "check_ids": ["demo-key-presence-v1"],
                             "expected_observable": "Une preuve liée aux octets capturés.", "success_condition": "Les prémisses sont établies ou qualifiées.",
                             "failure_condition": "Contexte périmé ou absent.", "deadline_seconds": 60},
            "authority_requested": "BOUNDED_AUTONOMY", "supersedes_proposal_id": None}


def inspection(store, snapshot_id, lang="en"):
    snapshot = store.snapshots.get(snapshot_id)
    artifacts = []
    for aid, metadata in snapshot["details"]["files"].items():
        content = store.snapshots.artifact(snapshot_id, aid)
        try:
            preview = content[:8192].decode("utf-8")
        except UnicodeDecodeError:
            preview = TEXT[lang]["binary"]
        artifacts.append({"artifact_id": aid, **metadata, "preview": preview, "truncated": len(content) > 8192})
    return {"snapshot": snapshot, "artifacts": artifacts,
            "objects": list(snapshot["details"]["objects"].values()),
            "event_count": store.status()["event_count"], "mode": store.plan().mode.value}


def run_demo(lang="en"):
    text = TEXTS[lang]
    scenarios = []
    with tempfile.TemporaryDirectory(prefix="principalloop-snapshots-") as folder:
        root = Path(folder).resolve()
        assert root.is_relative_to(Path(tempfile.gettempdir()).resolve())
        for case, expected in CASES:
            title, subtitle, explanation = text[case]
            workspace = root / case / "workspace"
            workspace.mkdir(parents=True)
            project = "principalloop-demo"
            human = Principal("operator", Role.HUMAN, project)
            director = Principal("director", Role.DIRECTOR, project, "DEMO-RUN")
            verifier = Principal("verifier", Role.VERIFIER, project)
            source = workspace / "orders.py"
            source.write_text(text["source"] + "IDEMPOTENCY_FIELD = 'idempotency_key'\n", encoding="utf-8", newline="\n")
            clock = FixedClock(datetime(2026, 10, 4, 11, tzinfo=timezone.utc))
            with Store(root / case / "state/control.sqlite3", workspace=workspace, clock=clock) as store:
                store.initialize({"schema_version": "0.1", "project_id": project, "mission_revision": 1, "goal_id": "G-1",
                                  "objective": "Comprendre quand une proposition doit être réexaminée.",
                                  "acceptance_criteria": ["Aucune activation sur une capture instable."], "scope": ["service"],
                                  "hard_constraints": ["Aucun effet réel ni appel de modèle."], "allowed_actions": ["SIMULATE"],
                                  "observable_sources": ["events"], "budget": {"max_tokens": 0, "max_wall_seconds": 60, "max_tool_calls": 0},
                                  "escalation_conditions": []}, human)
                store.snapshots.put_object(Document("H-1", "HYPOTHESIS", *text["H-1"]), human, expected_revision=0, event_id="H1")
                store.snapshots.put_object(Document("H-2", "HYPOTHESIS", *text["H-2"]), human, expected_revision=0, event_id="H2")
                if case == "mandatory":
                    store.snapshots.set_required(["H-2"], human, expected_revision=1, event_id="REQUIRED")
                snap = store.snapshots.capture({"F-1": "orders.py"}, ["H-1", "H-2"], human, event_id="CAPTURE")
                store.snapshots.record_evidence("E-1", snap["manifest"]["snapshot_id"], "F-1", "demo-key-presence-v1", verifier,
                                               lambda data: "PASS" if b"idempotency_key" in data else "FAIL", event_id="EVIDENCE")
                if case == "unstable":
                    store._fault = lambda phase: source.write_bytes(b"# changed during capture\n") if phase == "capture_after_first_pass" else None
                    snap = store.snapshots.capture({"F-1": "orders.py"}, ["H-1", "H-2"], human, event_id="CAPTURE-UNSTABLE")
                    store._fault = lambda _: None
                sid = snap["manifest"]["snapshot_id"]
                store.snapshots.start_review(sid, "REVIEW", director, event_id="REVIEW")
                store.snapshots.read_context("REVIEW", "H-1", director, event_id="READ-H1")
                if case == "served":
                    store.snapshots.read_context("REVIEW", "H-2", director, event_id="READ-H2")
                proposal = proposal_for(snap["manifest"])
                store.register_proposal(proposal, director, review_id="REVIEW", event_id="PROPOSAL")
                if case == "noise":
                    event = {"schema_version": "0.1", "project_id": project, "event_id": "OTHER-TASK", "event_type": "TASK_PROGRESS",
                             "observed_at": "2026-10-04T11:01:00Z", "causal_ids": [],
                             "payload": {"summary": text["event"], "reference_ids": []}}
                    store.record_event(event, Principal("executor", Role.EXECUTOR, project, "RUN"))
                if case in ("premise", "served", "mandatory", "omitted"):
                    oid = "H-1" if case == "premise" else "H-2"
                    store.snapshots.put_object(Document(oid, "HYPOTHESIS", *text["revised"]),
                                               human, expected_revision=1, event_id="REVISION")
                if case == "file":
                    source.write_bytes(b"# new working tree version\nREQUEST_FIELD = 'request_id'\n")
                assessment = store.snapshots.validate(proposal)
                if assessment["eligible"] is not expected:
                    raise RuntimeError(f"Demo scenario {case} did not match its independent expected result")
                changes = []
                for oid, before in snap["details"]["objects"].items():
                    after = store.snapshots.objects()[oid]
                    if before["sha256"] != after["sha256"]:
                        changes.append({"name": before["title"], "before": before["document"]["content"], "after": after["document"]["content"]})
                before_file = store.snapshots.artifact(sid, "F-1").decode("utf-8")
                after_file = source.read_text(encoding="utf-8")
                if before_file != after_file:
                    changes.append({"name": "orders.py", "before": before_file, "after": after_file})
                scenarios.append({"id": case, "title": title, "subtitle": subtitle, "explanation": explanation, "changes": changes,
                                  "limit": case == "omitted", "expected": expected, "matched": True,
                                  "validation": assessment, **inspection(store, sid, lang)})
    labels = TEXT[lang]
    return {"format_version": 1, "kind": "demo", "lang": lang, "title": labels["demo_title"], "subtitle": labels["demo_subtitle"],
            "scenarios": scenarios, "all_expected_results_observed": True, "limits": labels["demo_limits"]}
