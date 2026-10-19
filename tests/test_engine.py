import json
import pytest
from workbench.engine import Request, run, parse_review
from workbench.providers import Reply, ProviderError, DemoProvider


class Scripted:
    model = 'test-model'
    def __init__(self, replies):
        self.replies, self.prompts = iter(replies), []
    def complete(self, system, prompt, max_tokens):
        self.prompts.append((system, prompt, max_tokens))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return Reply(reply, 10, 20)


def review(findings=False):
    return json.dumps({'verdict': 'ready_for_human_review', 'findings': [{
        'severity':'high', 'location':'a.py:2', 'issue':'Division by zero',
        'suggestion':'Reject empty input'}] if findings else []})


def test_feedback_reaches_author_and_reviewer_reads_revision():
    author = Scripted(['first patch', 'revised patch'])
    reviewer = Scripted([review(True), review()])
    result = run(Request('fix', 'source', rounds=2), {'GPT':author, 'Claude':reviewer})
    assert result['status'] == 'human_review'
    assert result['calls'] == 4
    assert 'Division by zero' in author.prompts[1][1]
    assert 'revised patch' in reviewer.prompts[1][1]
    assert result['proposal'] == 'revised patch'
    assert not result['tests_executed']


def test_roles_can_be_reversed_and_stop_early():
    a, r = Scripted(['patch']), Scripted([review()])
    result = run(Request('fix', 'source', author='Claude', rounds=2), {'Claude':a,'GPT':r})
    assert result['calls'] == 2
    assert [e['provider'] for e in result['events']] == ['Claude','GPT']


def test_findings_override_positive_verdict_and_round_limit():
    result = run(Request('fix', 'source'), {'GPT':Scripted(['patch']), 'Claude':Scripted([review(True)])})
    assert result['status'] == 'needs_changes'
    assert result['calls'] == 2


@pytest.mark.parametrize('reply', ['no json', '{}', '{"verdict":"ready_for_human_review","findings":"none"}'])
def test_invalid_review_is_incomplete(reply):
    result = run(Request('fix', 'source'), {'GPT':Scripted(['patch']), 'Claude':Scripted([reply])})
    assert result['status'] == 'incomplete'


def test_provider_failure_preserves_completed_event_and_stops():
    result = run(Request('fix', 'source', rounds=2), {
        'GPT':Scripted(['patch']), 'Claude':Scripted([ProviderError('Claude unavailable')])})
    assert result['status'] == 'incomplete' and result['calls'] == 2
    assert len(result['events']) == 1


@pytest.mark.parametrize('kwargs', [{'rounds':3}, {'context':'x'*40001}, {'task':''}, {'max_tokens':1}])
def test_invalid_request_makes_no_calls(kwargs):
    args = {'task':'fix', 'context':'source', **kwargs}
    with pytest.raises(ValueError):
        run(Request(**args), {})


def test_demo_is_labelled_and_bounded():
    result = run(Request('fix', 'source', rounds=2), {n:DemoProvider(n) for n in ['GPT','Claude']})
    assert result['status'] == 'needs_changes' and result['calls'] == 4
    assert all('DEMO' in e['text'] for e in result['events'])
