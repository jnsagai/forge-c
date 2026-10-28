import sys
import unittest
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.dont_write_bytecode = True
sys.path.insert(0, '/home/jefferson/fabro_dashboard')
from server import FabroClient


class DelayedReply(BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(0.3)
        try:
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"running"}')
        except BrokenPipeError:
            pass

    def log_message(self,*args):
        pass


class RemoteTimeout(unittest.TestCase):
    def test_delayed_live_response_and_short_bounded_failure(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),DelayedReply)
        server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_port)
        try:
            with self.assertRaises(TimeoutError):
                FabroClient({'url':url,'request_timeout_seconds':0.1}).get('/live')
            self.assertEqual(FabroClient({'url':url,'request_timeout_seconds':1}).get('/live'),{'status':'running'})
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_malformed_or_unbounded_source_configuration_is_rejected(self):
        for value in [True,0,-1,61,float('nan'),float('inf'),'30',None]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                FabroClient({'url':'http://127.0.0.1:1','request_timeout_seconds':value})


if __name__=='__main__':unittest.main()
