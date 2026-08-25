from __future__ import annotations

from pathlib import Path

from evals.run_evals import evaluate_runs, load_normalized_runs
from whyback.evaluation_cases import SCENARIO_IDS, build_normalized_synthetic_runs


def test_all_synthetic_cases_execute_and_pass_behavior_contracts(
    tmp_path: Path,
) -> None:
    output = tmp_path / "normalized_runs.json"
    summaries = build_normalized_synthetic_runs(output)
    report = evaluate_runs(load_normalized_runs(output))

    assert tuple(item["scenario_id"] for item in summaries) == SCENARIO_IDS
    assert report.missing_scenario_ids == ()
    assert report.aggregate.run_count == 12
    for metric in (
        report.aggregate.scenario_contract_pass_rate,
        report.aggregate.relevant_tool_selection_rate,
        report.aggregate.irrelevant_mandatory_call_avoidance_rate,
        report.aggregate.tool_budget_compliance_rate,
        report.aggregate.final_verification_pass_rate,
        report.aggregate.evidence_grounding_rate,
        report.aggregate.limitation_propagation_rate,
        report.aggregate.graceful_degradation_success_rate,
        report.aggregate.next_best_action_rate,
        report.aggregate.population_percentile_contract_rate,
        report.aggregate.broad_context_warning_rate,
    ):
        assert metric.rate == 1.0
    by_id = {str(item["scenario_id"]): item for item in summaries}
    assert (
        by_id["insufficient_comparison_population"]["population_percentile_available"]
        is False
    )
    assert by_id["broad_category_decline"]["broad_context_warning_present"] is True
    assert by_id["broad_category_decline"]["next_best_action_id"] == "CATEGORY_WINBACK"
    assert report.aggregate.duplicate_call_rate.numerator == 0
    assert report.aggregate.unsupported_evidence_rate.numerator == 0
