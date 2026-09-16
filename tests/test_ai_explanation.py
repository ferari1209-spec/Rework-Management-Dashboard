import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
import pandas as pd
from app.services.ai_explanation import aggregate_summary, explain


class PersonalAI(unittest.TestCase):
    def test_summary_excludes_identifiers(self):
        frame = pd.DataFrame([{'site': 'SECRET SITE', 'serial': 'SECRET SERIAL', '담당자': 'SECRET NAME'}])
        result = dict(as_of='2026-09-16', inbound=3, completed=2, hours=1.5,
                      missing_hours=1, insufficient=2,
                      inventory=frame, quality=frame, anomalies=frame, repeated=frame)
        summary = aggregate_summary(result, '2026-09-01', '2026-09-16')
        self.assertNotIn('SECRET', json.dumps(summary))
        self.assertEqual(summary['기간내완료건수'], 2)

    @patch('app.services.ai_explanation.urllib.request.build_opener')
    def test_request_and_response(self, builder):
        response = MagicMock()
        response.read.return_value = json.dumps({'status': 'completed', 'output': [
            {'type': 'message', 'content': [{'type': 'output_text', 'text': '분석 결과'}]}]})
        builder.return_value.open.return_value.__enter__.return_value = response
        self.assertEqual(explain('test-key', {'완료': 2}, '종합 해설'), '분석 결과')
        request = builder.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.openai.com/v1/responses')
        body = json.loads(request.data)
        self.assertIs(body['store'], False)
        self.assertNotIn('test-key', request.data.decode())
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-key')

    @patch('app.services.ai_explanation.urllib.request.build_opener')
    def test_error_does_not_expose_secret(self, builder):
        builder.return_value.open.side_effect = HTTPError('https://api.openai.com',401,'SECRET',{},None)
        with self.assertRaises(ValueError) as exc:
            explain('test-key', {}, '종합 해설')
        self.assertNotIn('SECRET', str(exc.exception))
        self.assertIn('유효하지', str(exc.exception))

    @patch('app.services.ai_explanation.urllib.request.build_opener')
    def test_no_request_without_key(self, builder):
        with self.assertRaises(ValueError):
            explain('', {}, '종합 해설')
        builder.assert_not_called()
