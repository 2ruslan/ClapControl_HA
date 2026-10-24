import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import Mock, patch
from clap_control.main import Application
from clap_control.web import serve,IngressServer


class WebTests(unittest.TestCase):
    def test_ingress_peer_only(self):
        self.assertTrue(IngressServer.verify_request(None,None,('172.30.32.2',123)))
        self.assertFalse(IngressServer.verify_request(None,None,('127.0.0.1',123)))
        self.assertFalse(IngressServer.verify_request(None,None,('172.30.33.1',123)))

    def test_routes_and_json_csrf_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Application(directory,Mock())
            server=serve(app,('127.0.0.1',0))
            thread=threading.Thread(target=server.serve_forever)
            with patch.object(server,'verify_request',return_value=True):
                thread.start()
                try:
                    base=f'http://127.0.0.1:{server.server_port}'
                    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    for path in ('/','/app.js','/style.css','/api/settings','/api/status'):
                        with opener.open(base+path) as response:self.assertEqual(response.status,200)
                    request=urllib.request.Request(base+'/api/settings',data=b'{}',method='POST')
                    with self.assertRaises(urllib.error.HTTPError) as caught:opener.open(request)
                    self.assertEqual(caught.exception.code,403)
                    caught.exception.close()
                    request=urllib.request.Request(base+'/api/settings',data=json.dumps({'test_mode':True}).encode(),
                        headers={'Content-Type':'application/json','X-Clap-Control':'1'},method='POST')
                    with opener.open(request) as response:self.assertTrue(json.load(response)['test_mode'])
                finally:
                    server.shutdown();server.server_close();thread.join()
