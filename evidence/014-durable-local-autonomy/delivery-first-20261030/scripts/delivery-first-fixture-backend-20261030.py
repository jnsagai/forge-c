"""FIXTURE_ONLY protocol backend: never sends a generation request to Qwen."""
from pathlib import Path
import hashlib,json,time
import httpx
import uvicorn
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse,StreamingResponse
ROOT=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1/fixture-only')
app=FastAPI()
@app.get('/health')
async def health():return {'status':'ok','mode':'FIXTURE_ONLY_NO_GENERATION'}
@app.post('/apply-template')
@app.post('/tokenize')
async def measure(request:Request):
    path=request.url.path
    assert path in ('/apply-template','/tokenize')
    async with httpx.AsyncClient(timeout=30) as client:
        response=await client.post('http://127.0.0.1:11457'+path,json=await request.json())
    return JSONResponse(response.json(),status_code=response.status_code)
@app.post('/v1/chat/completions')
async def fixture(request:Request):
    body=await request.json()
    with (ROOT/'fixture-requests.jsonl').open('a') as f:
        f.write(json.dumps({'at':time.time(),'mode':'FIXTURE_ONLY','real_qwen_generation_calls':0,
                            'request_sha256':hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()})+'\n')
    text=json.dumps({'status':'BLOCKED','artifacts':[],'issues':['FIXTURE_ONLY: no model or candidate substituted'],
                     'next_action':'halt'})
    if body.get('stream'):
        def chunks():
            yield 'data: '+json.dumps({'id':'fixture-only','object':'chat.completion.chunk','created':int(time.time()),
                       'model':body['model'],'choices':[{'index':0,'delta':{'role':'assistant','content':text},
                                                         'finish_reason':None}]})+'\n\n'
            yield 'data: '+json.dumps({'id':'fixture-only','object':'chat.completion.chunk','created':int(time.time()),
                       'model':body['model'],'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]})+'\n\n'
            yield 'data: [DONE]\n\n'
        return StreamingResponse(chunks(),media_type='text/event-stream')
    return {'id':'fixture-only','object':'chat.completion','created':int(time.time()),'model':body['model'],
            'choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'stop'}]}
uvicorn.run(app,host='127.0.0.1',port=11461,log_level='warning')

