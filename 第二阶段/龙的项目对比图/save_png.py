import http.server, json, base64, sys

PORT = 8898
OUT = r'C:\Honey\对比图-研究范式.png'

class H(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers','*')
        self.end_headers()
    def do_POST(self):
        l=int(self.headers.get('Content-Length',0))
        d=json.loads(self.rfile.read(l))
        with open(OUT,'wb') as f:
            f.write(base64.b64decode(d['image']))
        print('Saved PNG to', OUT, file=sys.stderr)
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(b'OK')

http.server.HTTPServer(('',PORT),H).handle_request()
print('Done', file=sys.stderr)
