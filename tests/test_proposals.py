import copy
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import ProjectStore, make_handler
from proposal import CRITERIA
from scripts.make_test_pdf import make_pdf, PROPOSAL_PAGES, GUIDE_PAGES



def audit_fixture(document_id):
    checks = {key: {'status': 'unknown', 'summary': 'Belum dinilai pada fixture pengujian.',
                    'recommendation': 'Periksa sumber dan ketentuan yang relevan.', 'severity': 'none',
                    'evidence': []} for key in CRITERIA}
    checks['keselarasan'] = {'status': 'needs_revision', 'summary': 'Fixture: arah pertanyaan perlu diperjelas.',
        'recommendation': 'Fixture: rinci pertanyaan dan hubungannya dengan tujuan.', 'severity': 'major',
        'evidence': [{'document_id': document_id, 'pdf_page': 1, 'quote': PROPOSAL_PAGES[0][3]}]}
    return checks


class ProposalTests(unittest.TestCase):
    def setUp(self):
        credentials = patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': '', 'OPENAI_API_KEY': ''})
        credentials.start()
        self.addCleanup(credentials.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.tmp.name) / 'projects.sqlite3')
        self.project = self.store.create('Proposal sintetis untuk pengujian')
        self.doc = self.store.add_document(self.project['id'], 'proposal.pdf', make_pdf(PROPOSAL_PAGES), 'proposal')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.store))
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01), daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.path = f'/api/documents/{self.doc["id"]}/proposal'

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.tmp.cleanup()

    def call(self, path, payload=None, raw=None, headers=None):
        headers = dict(headers or {})
        if payload is not None:
            raw = json.dumps(payload).encode()
            headers['Content-Type'] = 'application/json'
        request = Request(self.base+path, data=raw, headers=headers)
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def ai(self, raw=None, **extra):
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'MOCK-KEY-NOT-REAL'}), patch(
            'proposal.request_structured', return_value=(raw or audit_fixture(self.doc['id']), 'MOCK-AUDITOR', {})):
            return self.call(self.path+'/audits', {'mode': 'ai', 'consent': True, **extra})

    def manual(self):
        return {'criterion': 'keselarasan', 'severity': 'major', 'summary': 'Catatan manual sintetis.',
                'recommendation': 'Perjelas pertanyaan penelitian.', 'actor': 'Peninjau uji',
                'evidence': [{'document_id': self.doc['id'], 'pdf_page': 1, 'quote': PROPOSAL_PAGES[0][3]}]}

    def test_dashboard_and_document_kinds_are_real_counts(self):
        self.store.add_document(self.project['id'], 'journal.pdf', make_pdf(PROPOSAL_PAGES))
        status, dashboard = self.call(f'/api/projects/{self.project["id"]}/dashboard')
        self.assertEqual(status, 200)
        self.assertEqual(dashboard['counts']['proposal'], 1)
        self.assertEqual(dashboard['counts']['journal'], 1)
        self.assertEqual(dashboard['counts']['open_issues'], 0)
        self.assertEqual(dashboard['proposal_status'], 'not_audited')
        health = self.call('/api/health')[1]
        self.assertEqual(health['version'], '0.3.0')
        self.assertEqual(health['ai_status'], 'not_configured')

    def test_local_structure_works_without_ai_and_does_not_grade_content(self):
        status, audit = self.call(self.path+'/audits', {'mode': 'structure'})
        self.assertEqual(status, 201, audit)
        self.assertEqual(audit['status'], 'structure_only')
        self.assertNotIn('checks', audit['result'])
        self.assertEqual([o['chapter'] for o in audit['result']['structure']['outline']], ['I', 'II', 'III'])
        self.assertEqual([o['pdf_page'] for o in audit['result']['structure']['outline']], [1, 2, 3])
        self.assertEqual(self.store.dashboard(self.project['id'])['proposal_status'], 'structure_only')
        self.assertEqual(ProjectStore(self.store.path).proposal_view(self.doc['id'])['audits'][0]['id'], audit['id'])

    def test_ai_unconfigured_does_not_create_fake_audit(self):
        status, result = self.call(self.path+'/audits', {'mode': 'ai', 'consent': True})
        self.assertEqual(status, 503)
        self.assertEqual(result['status'], 'not_configured')
        self.assertEqual(self.store.proposal_view(self.doc['id'])['audits'], [])
        self.assertEqual(self.store.proposal_issues(self.project['id']), [])

    def test_ai_consent_required(self):
        with patch('proposal.request_structured') as provider:
            self.assertEqual(self.call(self.path+'/audits', {'mode': 'ai'})[0], 400)
            provider.assert_not_called()

    def test_valid_draft_creates_actionable_issues_and_no_approval(self):
        status, audit = self.ai()
        self.assertEqual(status, 201, audit)
        self.assertEqual(audit['status'], 'draft_audit')
        self.assertEqual(set(audit['result']['checks']), set(CRITERIA))
        issues = self.store.proposal_issues(self.project['id'])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]['status'], 'open')
        self.assertTrue(issues[0]['fresh'])
        self.assertEqual(issues[0]['details']['evidence'][0]['pdf_page'], 1)
        self.assertNotIn('MOCK-KEY-NOT-REAL', json.dumps(audit))
        self.assertEqual(self.store.dashboard(self.project['id'])['proposal_status'], 'revisions_pending')

    def test_unknown_checks_never_imply_ready_for_review(self):
        raw = audit_fixture(self.doc['id'])
        raw['keselarasan'].update(status='unknown', severity='none', evidence=[])
        self.assertEqual(self.ai(raw)[0], 201)
        dashboard = self.store.dashboard(self.project['id'])
        self.assertEqual(dashboard['proposal_status'], 'unknown')
        self.assertEqual(dashboard['counts']['open_issues'], 0)

    def test_bibliography_is_not_treated_as_verified_source_content(self):
        raw = audit_fixture(self.doc['id'])
        raw['literatur'] = copy.deepcopy(raw['keselarasan'])
        raw['literatur'].update(status='adequate', severity='none')
        status, body = self.ai(raw)
        self.assertEqual(status, 502)
        self.assertIn('literatur asli', body['error'])

    def test_fabricated_quote_wrong_page_and_incomplete_join_rejected(self):
        for mutation in [lambda r: r['keselarasan']['evidence'][0].update(quote='Quotation that does not occur in the PDF.'),
                         lambda r: r['keselarasan']['evidence'][0].update(pdf_page=3),
                         lambda r: r.pop('etika')]:
            raw = audit_fixture(self.doc['id'])
            mutation(raw)
            status, body = self.ai(raw)
            self.assertEqual(status, 502, body)
        self.assertEqual(self.store.proposal_issues(self.project['id']), [])
        self.assertTrue(all(a['status'] == 'failed' for a in self.store.proposal_view(self.doc['id'])['audits']))

    def test_campus_compliance_requires_supplied_rule_evidence(self):
        raw = audit_fixture(self.doc['id'])
        raw['pedoman'] = copy.deepcopy(raw['keselarasan'])
        self.assertEqual(self.ai(raw)[0], 502)
        guide = self.store.add_document(self.project['id'], 'guide.pdf', make_pdf(GUIDE_PAGES), 'guideline')
        self.assertEqual(self.ai(raw, guideline_ids=[guide['id']])[0], 502)  # Missing guideline quote.
        raw['pedoman']['evidence'].append({'document_id': guide['id'], 'pdf_page': 1, 'quote': GUIDE_PAGES[0][1]})
        self.assertEqual(self.ai(raw, guideline_ids=[guide['id']])[0], 201)

    def test_guidelines_must_belong_to_same_project_and_selected_scope(self):
        other = self.store.create('Proyek lain')
        guide = self.store.add_document(other['id'], 'other.pdf', make_pdf(GUIDE_PAGES), 'guideline')
        self.assertEqual(self.ai(guideline_ids=[guide['id']])[0], 400)
        self.assertEqual(self.ai(guideline_ids=[self.doc['id']])[0], 400)
        self.assertEqual(self.ai(guideline_ids=[guide['id']]*2)[0], 400)

    def test_replaced_proposal_during_model_request_cannot_save_stale_audit(self):
        def provider(*args):
            self.store.add_document(self.project['id'], 'new.pdf', make_pdf(PROPOSAL_PAGES), 'proposal')
            return audit_fixture(self.doc['id']), 'MOCK-AUDITOR', {}
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'MOCK-ONLY'}), patch('proposal.request_structured', side_effect=provider):
            self.assertEqual(self.call(self.path+'/audits', {'mode': 'ai', 'consent': True})[0], 409)
        self.assertEqual(self.store.proposal_view(self.doc['id'])['audits'], [])

    def test_manual_issue_works_without_ai_and_events_persist(self):
        status, result = self.call(self.path+'/issues', self.manual())
        self.assertEqual(status, 201, result)
        issue = self.store.proposal_issues(self.project['id'])[0]
        for new_status in ['in_progress', 'addressed']:
            response, body = self.call(f'/api/issues/{issue["id"]}/events', {
                'status': new_status, 'actor': 'Peninjau lokal', 'note': 'Tindakan uji dicatat; belum verifikasi akademik.',
                'expected_event_id': issue['events'][0]['id']})
            self.assertEqual(response, 201, body)
            issue = self.store.proposal_issues(self.project['id'])[0]
            self.assertEqual(issue['status'], new_status)
        self.assertEqual(len(ProjectStore(self.store.path).proposal_issues(self.project['id'])[0]['events']), 3)
        self.assertNotIn('approved', self.store.dashboard(self.project['id'])['proposal_status'])

    def test_invalid_manual_evidence_and_missing_notes_rejected(self):
        payload = self.manual()
        payload['evidence'][0]['quote'] = 'Invented quotation that is not in the document.'
        self.assertEqual(self.call(self.path+'/issues', payload)[0], 400)
        payload = self.manual()
        payload['criterion'] = 'pedoman'
        self.assertEqual(self.call(self.path+'/issues', payload)[0], 400)
        self.assertEqual(self.call(self.path+'/issues', self.manual())[0], 201)
        issue = self.store.proposal_issues(self.project['id'])[0]
        for status, note in [('verified', 'Fake approval'), ('addressed', '')]:
            self.assertEqual(self.call(f'/api/issues/{issue["id"]}/events', {
                'status': status, 'note': note, 'actor': 'User', 'expected_event_id': issue['events'][0]['id']})[0], 400)

    def test_conflicting_issue_form_is_rejected(self):
        self.call(self.path+'/issues', self.manual())
        issue = self.store.proposal_issues(self.project['id'])[0]
        payload = {'status': 'in_progress', 'actor': 'User', 'note': 'Catatan pertama.', 'expected_event_id': issue['events'][0]['id']}
        self.assertEqual(self.call(f'/api/issues/{issue["id"]}/events', payload)[0], 201)
        self.assertEqual(self.call(f'/api/issues/{issue["id"]}/events', payload)[0], 409)

    def test_repeated_finding_reuses_id_and_reopens_with_history(self):
        self.ai()
        issue = self.store.proposal_issues(self.project['id'])[0]
        self.call(f'/api/issues/{issue["id"]}/events', {'status': 'addressed', 'actor': 'User', 'note': 'Ditangani pada fixture.',
                                                     'expected_event_id': issue['events'][0]['id']})
        self.ai()
        reopened = self.store.proposal_issues(self.project['id'])[0]
        self.assertEqual(reopened['id'], issue['id'])
        self.assertEqual(reopened['status'], 'open')
        self.assertEqual(len(reopened['events']), 3)

    def test_new_proposal_keeps_old_audits_but_marks_old_issues_inactive(self):
        self.ai()
        self.store.add_document(self.project['id'], 'revision.pdf', make_pdf(PROPOSAL_PAGES), 'proposal')
        old = self.store.proposal_view(self.doc['id'])
        self.assertFalse(old['is_active'])
        self.assertFalse(old['audits'][0]['fresh'])
        self.assertFalse(old['issues'][0]['fresh'])
        self.assertEqual(self.call(self.path+'/audits', {'mode': 'structure'})[0], 409)
        self.assertEqual(self.store.dashboard(self.project['id'])['counts']['open_issues'], 0)

    def test_missing_pdf_blocks_audit_and_issue_update(self):
        self.call(self.path+'/issues', self.manual())
        issue = self.store.proposal_issues(self.project['id'])[0]
        self.store.pdf_path(self.doc['id']).unlink()
        self.assertEqual(self.call(self.path+'/audits', {'mode': 'structure'})[0], 400)
        self.assertEqual(self.call(f'/api/issues/{issue["id"]}/events', {
            'status': 'addressed', 'actor': 'User', 'note': 'Cannot update missing source.',
            'expected_event_id': issue['events'][0]['id']})[0], 409)
        self.assertEqual(self.store.dashboard(self.project['id'])['proposal_status'], 'stale')

    def test_partial_structure_does_not_claim_missing_chapter(self):
        doc = self.store.add_document(self.project['id'], 'partial.pdf', make_pdf([PROPOSAL_PAGES[0], []]), 'proposal')
        status, body = self.call(f'/api/documents/{doc["id"]}/proposal/audits', {'mode': 'structure'})
        self.assertEqual(status, 201)
        self.assertEqual(body['result']['structure']['unread_pages'], [2])
        self.assertEqual(body['result']['structure']['missing_heading_candidates'], ['II', 'III'])
        self.assertNotIn('checks', body['result'])

    def test_upload_role_and_journal_analysis_separation(self):
        status, doc = self.call(f'/api/projects/{self.project["id"]}/documents', raw=make_pdf(GUIDE_PAGES),
            headers={'Content-Type': 'application/pdf', 'X-Filename': 'guide.pdf', 'X-Document-Kind': 'guideline'})
        self.assertEqual(status, 201)
        self.assertEqual(doc['kind'], 'guideline')
        self.assertEqual(self.call(f'/api/documents/{self.doc["id"]}/analyze', {'consent': True})[0], 400)
        self.assertEqual(self.call(f'/api/documents/{doc["id"]}/proposal')[0], 400)

    def test_cross_origin_audit_and_manual_issue_rejected(self):
        self.assertEqual(self.call(self.path+'/audits', {'mode': 'structure'}, headers={'Origin': 'https://evil.invalid'})[0], 403)
        self.assertEqual(self.call(self.path+'/issues', self.manual(), headers={'Origin': 'https://evil.invalid'})[0], 403)

    def test_selected_sources_only_are_sent_to_provider(self):
        selected = self.store.add_document(self.project['id'], 'selected.pdf', make_pdf(GUIDE_PAGES), 'guideline')
        other = self.store.add_document(self.project['id'], 'not-selected.pdf', make_pdf(GUIDE_PAGES), 'guideline')
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'MOCK-ONLY'}), patch(
            'proposal.request_structured', return_value=(audit_fixture(self.doc['id']), 'MOCK', {})) as provider:
            result = self.call(self.path+'/audits', {'mode': 'ai', 'consent': True, 'guideline_ids': [selected['id']]})
        self.assertEqual(result[0], 201)
        sent_ids = [d['document_id'] for d in provider.call_args.args[3]['untrusted_documents']]
        self.assertEqual(sent_ids, [self.doc['id'], selected['id']])
        self.assertNotIn(other['id'], sent_ids)

    def test_guideline_changed_during_audit_prevents_mixed_version_result(self):
        guide = self.store.add_document(self.project['id'], 'guide.pdf', make_pdf(GUIDE_PAGES), 'guideline')
        def provider(*args):
            self.store.pdf_path(guide['id']).write_bytes(b'%PDF-changed-after-audit-start')
            return audit_fixture(self.doc['id']), 'MOCK', {}
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'MOCK-ONLY'}), patch('proposal.request_structured', side_effect=provider):
            status, _ = self.call(self.path+'/audits', {'mode': 'ai', 'consent': True, 'guideline_ids': [guide['id']]})
        self.assertEqual(status, 409)
        self.assertEqual(self.store.proposal_view(self.doc['id'])['audits'], [])

    def test_old_documents_remain_journals_when_role_metadata_is_missing(self):
        journal = self.store.add_document(self.project['id'], 'legacy.pdf', make_pdf(PROPOSAL_PAGES))
        with self.store.connect() as db:
            db.execute('DELETE FROM document_roles WHERE document_id=?', (journal['id'],))
        reopened = ProjectStore(self.store.path)
        self.assertEqual(reopened.document(journal['id'])['kind'], 'journal')
        self.assertEqual(reopened.document(journal['id'])['sha256'], journal['sha256'])

    def test_structure_history_limit_does_not_hide_last_substantive_audit(self):
        status, audit = self.ai()
        self.assertEqual(status, 201)
        from proposal import audit_proposal
        status, result = audit_proposal(self.doc, [], 'structure')
        for _ in range(21):
            self.store.save_proposal_audit(self.doc['id'], 'structure', status, result)
        view = self.store.proposal_view(self.doc['id'])
        self.assertTrue(any(a['id'] == audit['id'] and a['fresh'] for a in view['audits']))
