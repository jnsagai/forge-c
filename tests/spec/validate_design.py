#!/usr/bin/env python3
"""Static design-contract consistency tests, NOT runtime acceptance tests."""
from __future__ import annotations
import json, re, sys, unittest
from pathlib import Path
import xml.etree.ElementTree as ET
try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    raise SystemExit("Install open-source test dependencies: pyyaml jsonschema") from exc

ROOT=Path(__file__).resolve().parents[2]
FEATURE=ROOT/'specs/002-self-healing-factory'
CONFIG=ROOT/'config/factory'

def cfg(name):
    return yaml.safe_load((CONFIG/name).read_text(encoding='utf8'))

class ForgeV04Design(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roles=cfg('agents.yaml')['agents']
        cls.catalog=cfg('mcp-registry.yaml')['server_catalog']
        cls.ops={f"{srv['id']}.{op['name']}":op for srv in cls.catalog for op in srv['ops']}

    def test_project_constitution(self):
        s=(ROOT/'.specify/memory/constitution.md').read_text()
        for needle in ['SKILL','MCP','supervisor','lessons','trace','offline','tokens']:
            self.assertIn(needle.lower(),s.lower())

    def test_all_twenty_role_skills(self):
        paths=list((ROOT/'.fabro/skills').glob('*/SKILL.md'))
        ids=[r['id'] for r in self.roles]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(len(ids),20)
        self.assertEqual(len(paths),len(ids))
        for role in self.roles:
            skill=ROOT/role['skill']
            self.assertTrue(skill.is_file(),role['id'])
            src=skill.read_text()
            self.assertTrue(src.startswith('---\n'),role['id'])
            match=re.match(r'^---\n(.*?)\n---',src,re.S)
            self.assertIsNotNone(match)
            meta=yaml.safe_load(match.group(1))
            self.assertEqual(meta['name'],role['id'])
            self.assertIn('Allowed MCP tools',src)
            self.assertIn('Mandatory compact exit format',src)
            self.assertTrue((ROOT/role['output_contract']).is_file())

    def test_swe_author_inspector_pairs(self):
        names={r['id']:r for r in self.roles}
        for i in range(1,7):
            self.assertIn(f'swe{i}-author',names)
            self.assertIn(f'swe{i}-inspector',names)
            self.assertTrue(names[f'swe{i}-inspector']['readonly'])
            self.assertNotEqual(names[f'swe{i}-author']['skill'],names[f'swe{i}-inspector']['skill'])
            self.assertTrue((ROOT/f'factory/release-manager/checklists/SWE.{i}.yaml').exists())

    def test_all_agent_tools_in_mcp_registry(self):
        self.assertEqual(len(self.catalog),9)
        self.assertEqual(len(self.ops),34)
        for role in self.roles:
            self.assertGreater(len(role['allowed_tools']),0,role['id'])
            for op in role['allowed_tools']:
                self.assertIn(op,self.ops,f'{role["id"]}: {op}')
                self.assertIn(role['id'],self.ops[op]['role_grants'],f'{role["id"]} ungranted {op}')
        for srv in self.catalog:
            self.assertEqual(srv['lifecycle'],'SPECIFIED_NOT_IMPLEMENTED')
            self.assertTrue(srv['open_source_only'])
            for op in srv['ops']:
                self.assertEqual(op['status'],'WRAPPER_TO_CREATE')
                self.assertGreater(op['timeout_seconds'],0)
                if op['mandatory']:
                    self.assertTrue(op['role_grants'],f"{srv['id']}.{op['name']} has no grantee")

    def test_readonly_roles_not_given_mutation(self):
        forbidden={'freeze_baseline','configure','compile','create_worktree','commit_candidate','retract_lesson'}
        for role in self.roles:
            if role['readonly']:
                for tool in role['allowed_tools']:
                    self.assertNotIn(tool.split('.')[-1],forbidden,f'{role["id"]}: {tool}')
                    if tool.endswith('.build_package'): self.assertEqual(role['id'],'release-manager')
                    if tool.endswith('.propose_lesson'): self.assertEqual(role['id'],'lessons-curator')

    def test_model_free_supervisor(self):
        pol=cfg('supervisor-policy.yaml')
        self.assertEqual(pol['mode'],'NO_MODEL_IN_HEALTH_POLL')
        self.assertGreaterEqual(pol['poll_interval_seconds'],pol['valid_poll_interval_seconds'][0])
        self.assertLessEqual(pol['poll_interval_seconds'],pol['valid_poll_interval_seconds'][1])
        self.assertEqual(pol['repair']['role'],'fabric-repair')
        self.assertEqual(pol['repair']['dispatch_if_fabro_down'],'external_local_runner')
        self.assertTrue(pol['repair']['rollback_on_regression'])
        self.assertTrue(pol['repair']['forbid_safety_policy_changes'])

    def test_audit_capture_and_view_policy(self):
        pol=cfg('trace-policy.yaml')
        names={'human','workflow','tools','ai','supervisor','repair','security','audit','metrics','knowledge'}
        self.assertEqual(set(pol['capture_levels']),names)
        self.assertEqual(set(pol['per_channel_retention_days']),names)
        self.assertEqual(set(pol['mandatory_minimum_levels']),{'audit','security'})
        self.assertFalse(pol['ai_hidden_reasoning_capture'])
        self.assertFalse(pol['ai_raw_prompt_response_capture'])
        self.assertTrue(pol['viewer_filters_do_not_change_capture'])
        for v in pol['mandatory_minimum_levels'].values():self.assertNotEqual(v,'OFF')

    def test_token_policy_enforced_in_design(self):
        pol=cfg('token-policy.yaml')
        self.assertTrue(pol['no_model_supervisor_poll'])
        self.assertTrue(pol['suppress_explanatory_narrative'])
        self.assertTrue(pol['reject_on_budget_exhaustion'])
        self.assertLessEqual(pol['max_tool_result_bytes'],4096)
        self.assertLessEqual(pol['max_validated_lessons'],3)
        for role in self.roles:
            self.assertGreater(role['max_stage_tokens'],0)
            self.assertLessEqual(role['max_mcp_output_bytes'],pol['max_tool_result_bytes'])

    def test_example_contracts(self):
        examples=list((FEATURE/'contracts').glob('*.example.json'))
        self.assertGreaterEqual(len(examples),7)
        for example in examples:
            schema=json.loads(example.with_name(example.name.replace('.example.json','.schema.json')).read_text())
            Draft202012Validator.check_schema(schema)
            instance=json.loads(example.read_text())
            errors=list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(instance))
            self.assertEqual(errors,[],example.name+': '+str(errors[:2]))

    def test_spec_and_task_traceability(self):
        spec=(FEATURE/'spec.md').read_text()
        tasks=(FEATURE/'tasks.md').read_text()
        for i in range(1,41):
            fr=f'FR-{i:03}'
            self.assertIn(fr,spec)
            self.assertIn(fr,tasks,f'{fr} missing tasks')
        for task in range(1,52):
            self.assertRegex(tasks,rf'T{task:03}\b')
        for name in ['plan.md','data-model.md','research.md','quickstart.md','acceptance-tests.md']:
            self.assertTrue((FEATURE/name).exists())
        for test in range(1,27):
            self.assertIn(f'AT-{test:02}',(FEATURE/'acceptance-tests.md').read_text())

    def test_dashboard_contract_and_filters(self):
        api=yaml.safe_load((FEATURE/'contracts/dashboard-api.openapi.yaml').read_text())
        self.assertEqual(api['openapi'],'3.1.0')
        paths=api['paths']
        for path in ['/api/v1/health','/api/v1/events','/api/v1/events/stream','/api/v1/runs','/api/v1/incidents','/api/v1/lessons','/api/v1/mcp','/api/v1/tokens','/api/v1/packages']:
            self.assertIn(path,paths)
            self.assertEqual(set(paths[path]),{'get'})
        for x in ['channel','min_level','run_id']:
            self.assertIn(x,{p['name'] for p in paths['/api/v1/events']['get']['parameters']})

    def test_release_package_survives(self):
        self.assertTrue((ROOT/'factory/release-manager/scripts/build_review_package.py').is_file())
        self.assertTrue((ROOT/'factory/release-manager/tests/test_packager.py').is_file())
        self.assertTrue((ROOT/'factory/release-manager/policies/release-package-policy.json').is_file())
        self.assertTrue((ROOT/'CLAUDE_START.md').is_file())
        self.assertIn('offline',(FEATURE/'plan.md').read_text().lower())

    def test_editable_drawio(self):
        file=ROOT/'architecture/Forge-C_Fabro_DarkFactory_v0.4.drawio'
        tree=ET.parse(file);diagrams=tree.getroot().findall('diagram')
        self.assertEqual(len(diagrams),11)
        for d in diagrams:
            model=d.find('mxGraphModel');self.assertIsNotNone(model)
            cells=model.find('root').findall('mxCell')
            nodes={cell.get('id') for cell in cells}
            self.assertEqual(len(nodes),len(cells),d.get('name'))
            self.assertGreater(len([cell for cell in cells if cell.get('vertex')=='1']),10)
            for cell in cells:
                if cell.get('edge')=='1':
                    self.assertIn(cell.get('source'),nodes)
                    self.assertIn(cell.get('target'),nodes)
        for name in ['08 Supervisor','09 SKILL','10 Human dashboard','11 Validated lessons']:
            self.assertTrue(any((d.get('name') or '').startswith(name) for d in diagrams))

    def test_legacy_workflow_not_mislabeled(self):
        status=(ROOT/'workflows/README.md').read_text()
        self.assertIn('legacy',status.lower())
        self.assertIn('not',status.lower())

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ForgeV04Design)
    outcome=unittest.TextTestRunner(verbosity=2).run(suite)
    if outcome.wasSuccessful():
        print('PASS: 14 static design tests. This does NOT validate runtime integrations.')
    raise SystemExit(0 if outcome.wasSuccessful() else 1)
