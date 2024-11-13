import asyncio
import network
import json
from microdot import Microdot, send_file, redirect

class ServerInfo:
    def __init__(self, ssid='', active=False):
        self.ssid = ssid
        self.active = active    

class WebServer:
    def __init__(self, ssid, pw, get_config, update_config):
        self.get_config = get_config
        self.update_config = update_config
        self.ssid = ssid
        self.password = pw
        self.ap = network.WLAN(network.AP_IF)
        self.app = Microdot()
        self.active = False
        self.server_task = None

        @self.app.route('/')
        async def index(request):
            return redirect('/config')

        @self.app.route('/config')
        async def config(request):
            return self.read_html('/server/index.html'), 200, {'Content-Type': 'text/html'}

        @self.app.route('/scripts/<path:path>')
        async def script(request, path):
            if '..' in path:
                # directory traversal is not allowed
                return 'Not found', 404
            return send_file('/server/scripts/' + path)

        @self.app.route('/data', methods=['GET', 'POST'])
        async def data(request):
            if request.method == 'POST':
                decoded = json.loads(request.body.decode('utf-8'))
                self.update_config(decoded)
                return 'Config data updated successfully!'
            return self.get_config()['decorated'], 200
    
    def get_info(self):
        return ServerInfo(ssid=self.ssid, active=self.active)

    def read_html(self, html_path):
        try:
            with open(html_path, 'r') as f:
                return f.read()
        except OSError:
            print("Error reading HTML file")
            return ""

    async def toggle_server(self):
        if self.active:
            print("Deactivating server...")
            self.ap.active(False)
            self.app.shutdown()
            if self.server_task:
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
            self.active = False
        else:
            print("Activating server...")
            self.ap.config(essid=self.ssid, password=self.password)
            self.ap.active(True)
            while not self.ap.active():
                await asyncio.sleep_ms(50)
            print("Access point active")
            print(self.ap.ifconfig())
            self.active = True
            self.server_task = asyncio.create_task(self.app.start_server(debug=True, port=80))