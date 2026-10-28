"""Owner-selected Qwen3.8 routes through existing local isolation and quality gates."""
import json
import tomllib

import pytest
from forge_factory.afo.diagnosis_packet import measure_request
from forge_factory.llm_gateway import sanitize_request, strip_reasoning
from forge_factory.lrtx import profile, stack

MODEL = 'qwen3.8:27b-q8_0'
PROFILE = 'local-rtx-v2-omniverse2-q38-quality'


def test_single_model_selection_rejects_old_models_and_cloud_fallback():
    p = profile.load(PROFILE)
    assert p['models']['default'] == MODEL and set(p['models']['allowed']) == {MODEL}
    args = dict(provider='ollama', code_model=None, acp_authors=None, acp_inspectors=None)
    assert profile.selection_issues(p, model=MODEL, **args) == []
    assert profile.selection_issues(p, model='qwen3.6:35b-a3b', **args) == ['PROFILE_MODEL_NOT_ALLOWED:qwen3.6:35b-a3b']
    assert 'PROFILE_PROVIDER_NOT_LOCAL:cloud' in profile.selection_issues(p, model=MODEL, **{**args, 'provider': 'cloud'})
    assert p['models']['allowed'][MODEL]['role_qualification'].startswith('NOT_QUALIFIED')


def test_rendered_fabro_default_and_provider_catalogue_use_only_q38(tmp_path):
    p = profile.load(PROFILE)
    config = tomllib.loads(stack.fabro_config({'profile': p, 'root': tmp_path, 'ports': p['deployment']['ports']}))
    assert config['run']['model'] == {'name': MODEL, 'provider': 'ollama'}
    providers = config['llm']['providers']
    assert set(providers) == {'ollama'} and set(providers['ollama']['models']) == {MODEL}
    assert providers['ollama']['default_model'] == MODEL
    assert providers['ollama']['models'][MODEL]['limits'] == {'context_tokens': 65536, 'max_output_tokens': 32768}
    legacy = profile.load('local-rtx-v2-omniverse2-q38')
    old = tomllib.loads(stack.fabro_config({'profile': legacy, 'root': tmp_path, 'ports': legacy['deployment']['ports']}))
    assert old['llm']['providers']['ollama']['models'][MODEL]['limits'] == {
        'context_tokens': 32768, 'max_output_tokens': 16384}


@pytest.mark.parametrize('limits', [
    {'fabro_context_tokens': True}, {'fabro_context_tokens': 131072},
    {'fabro_max_output_tokens': 65537}, {'fabro_context_tokens': 8192, 'fabro_max_output_tokens': 4096,
                                       'ollama': {'OLLAMA_CONTEXT_LENGTH': '4096'}},
])
def test_invalid_or_provider_incompatible_context_is_refused(tmp_path, limits):
    p = profile.load(PROFILE)
    p['runtime'].update(limits)
    with pytest.raises(ValueError, match='FABRO_'):
        stack.fabro_config({'profile': p, 'root': tmp_path, 'ports': p['deployment']['ports']})


def test_quality_reasoning_is_bounded_measured_and_never_persisted():
    p = profile.load(PROFILE)
    reasoning = json.loads(stack.gateway_reasoning(p))
    body = sanitize_request({'model': MODEL, 'max_tokens': 512, 'messages': [{'role': 'user', 'content': 'Bounded task'}]},
                            policy=reasoning)
    assert body['reasoning_effort'] == 'high' and body['max_tokens'] == 16896
    measured = measure_request(body)
    assert measured['input_tokens'] + body['max_tokens'] <= int(p['runtime']['ollama']['OLLAMA_CONTEXT_LENGTH'])
    clean, removed = strip_reasoning({'content': 'answer', 'reasoning_content': 'PRIVATE_REASONING'})
    assert removed and clean == {'content': 'answer'}


def test_model_selection_keeps_existing_engine_inspection_and_isolation_rules():
    p = profile.load(PROFILE)
    previous = profile.load('local-rtx-v2-omniverse2-q38')
    for key in ['structured', 'safec', 'network', 'admission']:
        assert p[key] == previous[key]
    assert p['admission']['max_inflight'] == 1
    assert p['runtime']['ollama']['OLLAMA_NUM_PARALLEL'] == '1'
    assert p['runtime']['ollama']['OLLAMA_MAX_LOADED_MODELS'] == '1'
