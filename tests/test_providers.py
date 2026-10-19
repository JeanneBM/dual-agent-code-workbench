import json
import httpx
import pytest
from workbench.providers import APIProvider, ProviderError


@pytest.mark.parametrize('name', ['GPT', 'Claude'])
def test_provider_contract_and_usage(name):
    seen = []
    def handler(request):
        seen.append(request)
        data = ({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'answer'}]}]}
                if name == 'GPT' else {'stop_reason':'end_turn','content':[{'type':'text','text':'answer'}]})
        return httpx.Response(200, json={**data,'usage':{'input_tokens':11,'output_tokens':12}})
    p = APIProvider(name,'selected-model','secret', httpx.Client(transport=httpx.MockTransport(handler)))
    reply = p.complete('system','source',2000)
    assert reply.text == 'answer' and reply.input_tokens == 11
    body = json.loads(seen[0].content)
    assert body['model'] == 'selected-model' and 'secret' not in seen[0].content.decode()
    if name == 'GPT':
        assert body['store'] is False and body['max_output_tokens'] == 2000
        assert seen[0].url.host == 'api.openai.com'
    else:
        assert body['max_tokens'] == 2000 and body['messages'][0]['content'] == 'source'
        assert seen[0].headers['anthropic-version'] == '2023-06-01'


@pytest.mark.parametrize('name,data', [('GPT', {'status':'incomplete'}), ('Claude', {'stop_reason':'max_tokens'})])
def test_truncation_never_passes(name, data):
    client = httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data)))
    with pytest.raises(ProviderError, match='incomplete'):
        APIProvider(name,'model','secret',client).complete('s','p',512)


def test_error_body_never_leaks_credentials():
    client = httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(401,text='secret-sensitive-body')))
    with pytest.raises(ProviderError) as error:
        APIProvider('GPT','model','secret',client).complete('s','p',512)
    assert 'secret' not in str(error.value)


def test_missing_config_fails_before_call():
    with pytest.raises(ValueError):
        APIProvider('GPT','','')
