import json
import time
import threading
import requests
import websocket
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class QuotexClient:
    def __init__(self, email, password, strategy_wrapper):
        self.email = email
        self.password = password
        self.strategy_wrapper = strategy_wrapper
        self.ws = None
        self.session = requests.Session()
        self.base_url = "https://quotex.io"
        self.ws_url = None
        self.csrf_token = None
        self.authenticated = False

        # Browser headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })

    def _get_csrf_and_cookies(self):
        try:
            resp = self.session.get(self.base_url, timeout=10)
            resp.raise_for_status()
            if 'csrf-token' in resp.cookies:
                self.csrf_token = resp.cookies['csrf-token']
            else:
                import re
                match = re.search(r'<meta name="csrf-token" content="([^"]+)"', resp.text)
                if match:
                    self.csrf_token = match.group(1)
            self.cookies = self.session.cookies.get_dict()
            logger.info("CSRF token and cookies obtained")
            return True
        except Exception as e:
            logger.error(f"Failed to fetch main page: {e}")
            return False

    def _login(self):
        login_url = f"{self.base_url}/api/login"
        payload = {'email': self.email, 'password': self.password, 'remember': '1'}
        headers = {
            'X-CSRF-Token': self.csrf_token,
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
            'Origin': self.base_url,
            'Referer': f"{self.base_url}/",
        }
        try:
            resp = self.session.post(login_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if data.get('status') == 'success':
                logger.info("Login successful")
                self.ws_url = self._get_websocket_url()
                self.authenticated = True
                return True
            else:
                logger.error(f"Login failed: {data}")
                return False
        except Exception as e:
            logger.error(f"Login request error: {e}")
            return False

    def _get_websocket_url(self):
        try:
            resp = self.session.get(self.base_url)
            import re
            match = re.search(r'wss://[^"\']+quotex[^"\']+', resp.text)
            if match:
                return match.group(0)
        except:
            pass
        return "wss://ws.quotex.io/"

    def _subscribe_to_candles(self):
        # You MUST adjust this based on the actual Quotex WebSocket API.
        # Inspect the browser's Network tab to see the exact subscription format.
        assets = ["EURUSD", "GBPUSD", "USDJPY"]  # replace with your pairs
        for asset in assets:
            sub_msg = {
                "type": "subscribe",
                "channel": "candles",
                "asset": asset,
                "period": 60   # 1 minute candles – change as needed
            }
            self.ws.send(json.dumps(sub_msg))
            logger.info(f"Subscribed to {asset} candles")
            time.sleep(0.2)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            # ------------------------------------------------------------------
            # This is where you need to adapt the message parsing to the real Quotex format.
            # The structure below is a guess. Replace with what you see in the browser.
            # ------------------------------------------------------------------
            if 'candle' in data and 'asset' in data:
                candle_raw = data['candle']
                asset = data['asset']
                # Convert time (assume Unix timestamp)
                try:
                    candle_time = datetime.fromtimestamp(candle_raw['time'])
                except:
                    candle_time = datetime.now()
                candle = {
                    'time': candle_time,
                    'open': float(candle_raw['open']),
                    'high': float(candle_raw['high']),
                    'low': float(candle_raw['low']),
                    'close': float(candle_raw['close']),
                    'volume': float(candle_raw.get('volume', 0))
                }
                self.strategy_wrapper.on_candle(asset, candle)
            else:
                logger.debug(f"Received non-candle: {message}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info("WebSocket closed")
        self.authenticated = False

    def _on_open(self, ws):
        logger.info("WebSocket opened")
        self._subscribe_to_candles()

    def start(self):
        if not self._get_csrf_and_cookies():
            return
        if not self._login():
            return

        headers = {
            'User-Agent': self.session.headers['User-Agent'],
            'Origin': self.base_url,
            'Referer': f"{self.base_url}/",
            'Cookie': '; '.join([f"{k}={v}" for k, v in self.session.cookies.get_dict().items()]),
            'X-CSRF-Token': self.csrf_token,
        }

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        wst = threading.Thread(target=self.ws.run_forever, kwargs={'ping_interval': 30})
        wst.daemon = True
        wst.start()
        logger.info("WebSocket thread started")

    def stop(self):
        if self.ws:
            self.ws.close()
