"""Tests for WhyBack's actions behavior."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from whyback.agent.actions import (
    EXPECTED_ACTION_IDS,
    ActionCatalogError,
    ActionId,
    load_action_catalog,
)


def _catalog_document() -> dict[str, object]:
    """Return a mutable action-catalog document for validation tests."""

    with Path("configs/actions.yaml").open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    assert isinstance(document, dict)
    return document


def test_checked_in_catalog_is_the_exact_human_review_allowlist() -> None:
    """Verify that checked in catalog is the exact human review allowlist."""

    catalog = load_action_catalog()

    assert catalog.catalog_version == 1
    assert catalog.action_ids == EXPECTED_ACTION_IDS
    assert len(catalog.actions) == 6
    assert all(action.human_review_required for action in catalog.actions)
    assert all(action.success_metric.description for action in catalog.actions)
    assert all(action.experiment.holdout_fraction > 0 for action in catalog.actions)


def test_supported_actions_have_evidence_rules_and_insufficient_is_fallback() -> None:
    """Verify supported-action evidence rules and the insufficient fallback."""

    catalog = load_action_catalog()

    for action in catalog.actions:
        if action.action_id is ActionId.INSUFFICIENT_EVIDENCE:
            assert action.fallback_only
            assert action.evidence_prerequisites == ()
        else:
            assert not action.fallback_only
            assert action.evidence_prerequisites
            assert action.contraindications


def test_catalog_and_nested_models_are_immutable() -> None:
    """Verify that catalog and nested models are immutable."""

    catalog = load_action_catalog()

    with pytest.raises(ValidationError):
        catalog.catalog_version = 2  # type: ignore[misc]
    with pytest.raises(ValidationError):
        catalog.actions[0].description = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        catalog.actions[0].success_metric.name = "changed"  # type: ignore[misc]


def test_get_rejects_action_outside_allowlist() -> None:
    """Verify that get rejects action outside allowlist."""

    catalog = load_action_catalog()

    assert catalog.get("MONITOR").action_id is ActionId.MONITOR
    with pytest.raises(ActionCatalogError, match="Unknown action ID"):
        catalog.get("SEND_DISCOUNT_EMAIL")


@pytest.mark.parametrize("mutation", ["missing", "unexpected", "duplicate"])
def test_loader_fails_closed_when_ids_are_not_exact(
    tmp_path: Path, mutation: str
) -> None:
    """Verify that loader fails closed when ids are not exact."""

    document = _catalog_document()
    actions = document["actions"]
    assert isinstance(actions, list)
    if mutation == "missing":
        actions.pop()
    elif mutation == "unexpected":
        action = actions[0]
        assert isinstance(action, dict)
        action["action_id"] = "SEND_DISCOUNT_EMAIL"
    else:
        duplicate = actions[0]
        assert isinstance(duplicate, dict)
        actions[1] = duplicate.copy()
    path = tmp_path / "actions.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(ActionCatalogError, match="Invalid action catalog"):
        load_action_catalog(path)


def test_loader_rejects_extra_fields_and_non_mapping_roots(tmp_path: Path) -> None:
    """Verify that loader rejects extra fields and non mapping roots."""

    document = _catalog_document()
    document["unreviewed_policy"] = True
    extra_path = tmp_path / "extra.yaml"
    extra_path.write_text(yaml.safe_dump(document), encoding="utf-8")
    list_path = tmp_path / "list.yaml"
    list_path.write_text("- not\n- a\n- catalog\n", encoding="utf-8")

    with pytest.raises(ActionCatalogError, match="extra_forbidden"):
        load_action_catalog(extra_path)
    with pytest.raises(ActionCatalogError, match="root must be a mapping"):
        load_action_catalog(list_path)
