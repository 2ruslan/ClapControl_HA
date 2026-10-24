"""Exercise real HTTP serialization, auth, error handling and timeout."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import unittest
from clap_control.scenes import HomeAssistant, APIError


class APITests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.state = 'unknown'
        self.code = 200
        self.delay = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass

            def do_GET(self):
                self.reply()

            def do_POST(self):
                self.reply()

            def reply(self):
                length = int(self.headers.get('Content-Length', '0'))
                data = json.loads(self.rfile.read(length)) if length else None
                owner.calls.append((self.command, self.path, self.headers.get('Authorization'), data))
                time.sleep(owner.delay)
                self.send_response(owner.code)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                scene = {'entity_id':'scene.a', 'state':owner.state, 'attributes':{'friendly_name':'Evening'}}
                payload = [scene] if self.path == '/states' else scene
                try: self.wfile.write(json.dumps(payload).encode())
                except ConnectionError: pass

        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.addCleanup(self.cleanup_server)
        self.api = HomeAssistant('test-token',f'http://127.0.0.1:{self.server.server_port}',timeout=.1)

    def cleanup_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_protocol(self):
        self.assertEqual(self.api.scenes(),[{'entity_id':'scene.a','name':'Evening','available':True}])
        self.api.activate('scene.a')
        self.api.request('POST','/events/clap_control_triggered',{'scene':'scene.a'})
        self.assertEqual([c[1] for c in self.calls],['/states','/states/scene.a','/services/scene/turn_on','/events/clap_control_triggered'])
        self.assertTrue(all(c[2]=='Bearer test-token' for c in self.calls))
        self.assertEqual(self.calls[2][3],{'entity_id':'scene.a'})

    def test_missing_and_service_failure(self):
        for code in (404,401,503):
            self.code=code
            with self.assertRaises(APIError) as caught:self.api.activate('scene.a')
            self.assertIn(str(code),str(caught.exception))
        self.assertTrue(all(c[0]=='GET' for c in self.calls))

    def test_timeout_and_recovery(self):
        self.delay=.3
        start=time.monotonic()
        with self.assertRaises(APIError):self.api.scenes()
        self.assertLess(time.monotonic()-start,1)
        self.delay=0
        self.assertEqual(len(self.api.scenes()),1)
