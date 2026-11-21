import asyncio
from uuid import uuid4
import sqlalchemy as sa
import httpx2
from payscope.main import app
from payscope.seed import seed_hr_user, DEMO_HR_EMAIL
from payscope.config import SeedSettings
from payscope.models import hr_users
from payscope.agents import runs
from payscope.agents.schemas import RunRequest
from payscope.agents.runtime import DATABASE_LEASE

async def main():
 async with app.router.lifespan_context(app):
  async with app.state.engine.begin() as db:
   user = await seed_hr_user(db, SeedSettings().demo_hr_password.get_secret_value())
  async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url='https://testserver') as client:
   response = await client.post('/api/auth/sign-in',json={'email':DEMO_HR_EMAIL,'password':SeedSettings().demo_hr_password.get_secret_value()})
   assert response.status_code == 200
   headers={'X-CSRF-Token':response.json()['csrf_token']}
   async with app.state.session_factory() as db:
    run,_=await runs.admit_run(db,RunRequest(question='Observability deletion verification'),user_id=user,auth_session_id=None,idempotency_key=uuid4(),runtime_fingerprint='observability-test',runtime_limits={},start_timeout=DATABASE_LEASE)
   token=uuid4()
   async with app.state.session_factory() as db: await runs.claim_run(db,run.id,token,DATABASE_LEASE)
   async with app.state.session_factory() as db: await runs.finalize_run(db,run.id,token,status='completed',answer='Verification complete.',payload={})
   path=f'/api/admin/agent-runs/{run.id}'
   before=(await client.get(path)).json()
   assert before['id']==str(run.id), before
   assert (await client.delete(f'/api/agent/conversations/{run.conversation_id}',headers=headers)).status_code==204
   after=(await client.get(path)).json()
   assert after['messages']==before['messages'] and after['source_deleted_at']
   listing=await client.get('/api/admin/agent-runs',params={'run_id':str(run.id)})
   assert listing.status_code==200, listing.text
   assert len(listing.json()['items'])==1
   for suffix in ['/events','/tools']:
    assert (await client.get(path+suffix)).status_code==200
   assert (await client.get(f'/api/agent/conversations/{run.conversation_id}')).status_code==404
   assert (await client.post(f'/api/agent/conversations/{run.conversation_id}/restore',headers=headers)).status_code==204
   assert not (await client.get(path)).json()['source_deleted_at']
   await client.delete(f'/api/agent/conversations/{run.conversation_id}',headers=headers)
   await client.post('/api/auth/sign-out',headers=headers)
   print('PASS: admin run list/detail/events/tools survive source deletion; restore and user visibility checked.')
asyncio.run(main())
