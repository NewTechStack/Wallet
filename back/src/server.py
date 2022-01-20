from gevent import monkey;  monkey.patch_all()
import os
import json
from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler
from werkzeug.debug import DebuggedApplication
from bottle import Bottle, run, route, response, request, hook, error, BaseRequest
from Controller.basic import ret, check, callnext
from Controller.routes import *
app = Bottle()
BaseRequest.MEMFILE_MAX = 1024 * 1024 * 256

host =      str(os.getenv('API_HOST', '0.0.0.0'))
port =      int(os.getenv('API_PORT', 8080))
weba =      str(os.getenv('API_WEBA', '*'))
mod =       str(os.getenv('API_MOD', 'PROD'))

call = lambda x = [] , ws = False, raw = False : callnext(request, response).call(x, ws, raw)

@app.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = weba
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = '*'

def error(error):
    toret = ret(request.path, check.json(request))
    toret.add_error(error.body, int(error.status.split(" ")[0]))
    response.content_type = 'application/json'
    return json.dumps(toret.ret())

if __name__ == '__main__':
    setuproute(app, call)
    app.error_handler = {500: error, 405: error, 404: error}
    server = WSGIServer((host, port), DebuggedApplication(app), handler_class=WebSocketHandler)
    print(f"\nRunning @ http://{host}:{port}")
    server.serve_forever()
    server.serve_forever()
