import http.server
import json
import base64
import os

PORT = 8898
OUTPUT = r'C:\Honey\对比图-研究范式.png'

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = self.rfile.read(length)
        data = json.loads(body.decode('utf-8'))
        b64 = data['image']
        img_bytes = base64.b64decode(b64)
        with open(OUTPUT, 'wb') as f:
            f.write(img_bytes)
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(b'OK')
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

with http.server.HTTPServer(('', PORT), Handler) as s:
    print(f'Serving on {PORT}')
    s.handle_request()
    print('Saved!')
