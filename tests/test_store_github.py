import httpx
import pytest
from workbench.store import Store
from workbench.github import load_pr, GitHubError


def test_history_roundtrip_and_deletion(tmp_path):
    store = Store(tmp_path/'history.sqlite')
    record = {'id':'abc','created':'now','events':[{'text':'proposal'}]}
    store.save(record)
    assert store.get('abc') == record and store.list() == [('abc','now')]
    store.delete('abc')
    assert store.get('abc') is None


def github_client(changed=False, binary=False):
    reads = []
    def handler(r):
        assert r.url.host == 'api.github.com'
        if r.url.path.endswith('/files'):
            return httpx.Response(200,json=[{'patch':None if binary else '@@ test', 'status':'modified'}])
        if r.headers['accept'] == 'application/vnd.github.diff':
            return httpx.Response(200,text='diff --git a/a.py b/a.py\n+change')
        reads.append(r)
        return httpx.Response(200,json={'title':'Fix','body':'criteria','changed_files':1,
            'head':{'sha':'new' if changed and len(reads)>1 else 'head'}, 'base':{'sha':'base'}})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_pr_snapshot_includes_identity():
    context = load_pr('https://github.com/o/r/pull/1', client=github_client())
    assert 'Head: head' in context and 'Base: base' in context and '+change' in context


@pytest.mark.parametrize('url', ['http://localhost/pull/1','https://evil.com/o/r/pull/1',
                                    'https://github.com/o/r/pull/1?redirect=evil'])
def test_only_github_pr_urls_are_accepted(url):
    with pytest.raises(GitHubError):
        load_pr(url)


@pytest.mark.parametrize('kwargs', [{'changed':True}, {'binary':True}])
def test_incomplete_or_changed_snapshot_rejected(kwargs):
    with pytest.raises(GitHubError):
        load_pr('https://github.com/o/r/pull/1',client=github_client(**kwargs))
