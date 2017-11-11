import time
import hmac, hashlib
import urllib.request
import base64, json
from typing import Optional
from collections import OrderedDict

from config import api_url, public_key, private_key


class RESTInterface:
    """
    AUD prices should be to at most 2 decimal places.
    Prices are fixed point integers such that $1 is 10^8.

    Order status values:
        New
        Placed
        Failed
        Error
        Cancelled
        Partially Cancelled
        Fully Matched
        Partially Matched
    """

    def __init__(self, public_key, private_key):
        """
        public_key: btcmarkets public api key
        private_key: btcmarkets base64-encoded private api key
        """
        self.key = public_key
        self.secret = base64.b64decode(private_key)

    def request(self, path: str, data: str = None):
        """
        path: the request path to append to the base API url
        data: a dictionary of data to send with in the request.
              If data is None, a GET request is sent, POST otherwise.
        """
        timestamp = int(time.time() * 1000)
        
        payload = f"{path}\n{timestamp}\n"
        if data is not None:
            payload += data
            data = data.encode()
        payload = payload.encode("utf-8")
        signature = base64.b64encode(hmac.new(self.secret, payload, digestmod=hashlib.sha512).digest())
        header = {
            'Accept': 'application/json',
            'Accept-Charset': 'UTF-8',
            'Content-Type': 'application/json',
            'apikey': self.key,
            'timestamp': timestamp,
            'signature': signature
        }

        req = urllib.request.Request(api_url + path, data=data, headers=header)
        return json.load(urllib.request.urlopen(req))

    def balance(self):
        """
        The balance of this account.
        Returns: a list of balances per currency each of the form:
                 {'balance': int, 'pendingFunds': int, 'currency': str}
        """
        return self.request("/account/balance")

    def fee(self, instrument: str, currency: str):
        """
        The fee associated with the given market on this account:
        Returns: {'success': bool, 'errorCode': ?, 'errorMessage': ?',
                  'tradingFeeRate': int, 'volume30Day': int}
        """
        return self.request(f"/account/{instrument}/{currency}/tradingfee")

    def market_tick(self, instrument: str, currency: str):
        """
        The given market's current tick.
        Returns: {'bestBid': float, 'bestAsk': float, 'lastPrice': float,
                  'currency': str, 'instrument': str, 'timestamp': int,
                  'volume24h': float}
        """
        return self.request(f"/market/{instrument}/{currency}/tick")

    def market_orderbook(self, instrument: str, currency: str):
        """
        The given market's current orderbook.
        Returns: a list of pairs of floats [price, amount].
        """
        return self.request(f"/market/{instrument}/{currency}/orderbook")

    def market_trades(self, instrument: str, currency: str, since_id: Optional[int] = None):
        """
        The given market's latest trades, optionally since the specified trade.
        Returns: a list of trades of the form:
                 {'tid': int, 'amount': int, 'price': float, timestamp: int}.
        """
        since = "" if since_id is None else f"?since={since_id}"
        return self.request(f"/market/{instrument}/{currency}/trades{since}")
    
    def create_order(self, instrument: str, currency: str,
                     price: int, volume: int,
                     order_side: str, order_type: str):
        data = (f'{{"currency":"{currency}","instrument":"{instrument}",'
                f'"price":{price},"volume":{volume},"orderSide":"{order_side}",'
                f'"ordertype":"{order_type}","clientRequestId":"NA"}}')
        return self.request("/order/create", data)

    def market_bid(self, instrument: str, currency: str, volume: int):
        return self.create_order(instrument, currency, 0, volume, "Bid", "Market")

    def market_ask(self, instrument: str, currency: str, volume: int):
        return self.create_order(instrument, currency, 0, volume, "Ask", "Market")

    def limit_bid(self, instrument: str, currency: str, price: int, volume: int):
        return self.create_order(instrument, currency, price, volume, "Bid", "Limit")

    def limit_ask(self, instrument: str, currency: str, price: int, volume: int):
        return self.create_order(instrument, currency, price, volume, "Ask", "Limit")


interface = RESTInterface(public_key, private_key)
