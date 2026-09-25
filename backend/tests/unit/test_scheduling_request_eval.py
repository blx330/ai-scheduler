"""The eval set must agree with the service's own rules. Running the harness with
an oracle parser that returns each case's expected output has to score 100%;
otherwise a label is wrong and live accuracy numbers would be meaningless."""

from scripts.eval_scheduling_parser import OracleParser, load_cases, run_eval


def test_eval_set_has_about_twenty_cases_with_both_outcomes() -> None:
    cases = load_cases()

    assert 20 <= len(cases) <= 30
    assert len({case.id for case in cases}) == len(cases)
    outcomes = {case.expected_outcome for case in cases}
    assert outcomes == {"accepted", "rejected"}


def test_oracle_scores_perfectly() -> None:
    cases = load_cases()
    report = run_eval(cases, OracleParser(cases))

    failures = [result for result in report.results if not (result.exact_match and result.outcome_correct)]
    assert failures == []
    assert report.exact_match_accuracy == 1.0
    assert report.outcome_accuracy == 1.0
    assert all(value == 1.0 for value in report.field_accuracy.values())
