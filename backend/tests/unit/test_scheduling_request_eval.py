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


class _QuotaAfter:
    """Answers like the oracle for the first `limit` calls, then acts rate-limited."""

    version = "quota-limited"

    def __init__(self, cases, limit: int) -> None:
        self.oracle = OracleParser(cases)
        self.limit = limit
        self.calls = 0

    def parse(self, text, context):
        from app.infrastructure.integrations.llm.scheduling_request_parser import SchedulingRequestUpstreamError

        self.calls += 1
        if self.calls > self.limit:
            raise SchedulingRequestUpstreamError("429 RESOURCE_EXHAUSTED")
        return self.oracle.parse(text, context)


def test_quota_exhaustion_keeps_finished_cases_and_resume_completes_the_run() -> None:
    cases = load_cases()
    first = run_eval(cases, _QuotaAfter(cases, limit=5), sleep=lambda _: None)

    assert first.incomplete
    assert [result.id for result in first.results] == [case.id for case in cases[:5]]

    second_parser = _QuotaAfter(cases, limit=100)
    second = run_eval(cases, second_parser, sleep=lambda _: None, previous=first.results)

    assert not second.incomplete
    assert second_parser.calls == len(cases) - 5
    assert [result.id for result in second.results] == [case.id for case in cases]
    assert second.exact_match_accuracy == 1.0
