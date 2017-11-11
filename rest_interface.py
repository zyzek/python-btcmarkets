import time
import hmac, hashlib
import urllib.request
import base64, json
from typing import Optional, List
from collections import OrderedDict

from config import api_url


class RESTInterface:
    """
    AUD prices should be to at most 2 decimal places.
    Prices are fixed point decimals such that $1 (or whatever) is 10^8.

    Throttles:
    25 calls per 10 seconds:
        create_order, market_bid, market_ask, limit_bid, limit_ask
        cancel_order
        order_detail, order_open_history
        balance
        market_tick, market_orderbook, market_trades

    10 calls per 10 seconds:
        order_history, order_trade_history
        fee
        withdraw_crypto, withdraw_eft
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

    def balances(self):
        """
        The balance of this account.
        Returns: a list of balances per currency each of the form:
                 {'balance': int, 'pendingFunds': int, 'currency': str}
        """
        return self.request("/account/balance")

    def balance(self, currency: str):
        """
        The current balance of this account in the given currency.
        """
        balance = [b['balance'] for b in self.balances() \
                   if b['currency'] == currency]
        if len(balance) == 0:
            return 0
        return balance[0]

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

    def best_ask(self, instrument: str, currency: str):
        """
        The current lowest ask price in the given market.
        """
        return self.market_tick(instrument, currency)['bestAsk']

    def best_bid(self, instrument: str, currency: str):
        """
        The current highest bid price in the given market.
        """
        return self.market_tick(instrument, currency)['bestBid']

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
        """
        Creates a market order with the specified parameters:
            instrument: the base currency
            currency:   the quoted currency
            price:      the price in currency per unit of instrument
            volume:     a quantity of the instrument
            order_side: "Bid" or "Ask"
            order_type: "Market" or "Limit".

        Returns: {'success': bool, 'errorCode': int, 'errorMessage': str,
                  'id': int, 'clientRequestId': str}

        "Market"-type orders will ignore the price parameter, filling at the best
        available price.
        Currently the "clientRequestId" data parameter is unused.
        """
        data = (f'{{"currency":"{currency}","instrument":"{instrument}",'
                f'"price":{price},"volume":{volume},"orderSide":"{order_side}",'
                f'"ordertype":"{order_type}","clientRequestId":"NA"}}')
        return self.request("/order/create", data)

    def market_bid(self, instrument: str, currency: str, volume: int):
        """Bid for a volume in a market at the best available price."""
        return self.create_order(instrument, currency, 0, volume, "Bid", "Market")

    def market_ask(self, instrument: str, currency: str, volume: int):
        """Ask for a volume in a market at the best available price."""
        return self.create_order(instrument, currency, 0, volume, "Ask", "Market")

    def limit_bid(self, instrument: str, currency: str, price: int, volume: int):
        """Bid for a volume in a market at the specified price."""
        return self.create_order(instrument, currency, price, volume, "Bid", "Limit")

    def limit_ask(self, instrument: str, currency: str, price: int, volume: int):
        """Ask for a volume in a market at the specified price."""
        return self.create_order(instrument, currency, price, volume, "Ask", "Limit")

    def cancel_order(self, order_ids: List[int]):
        """
        Cancel the specified list of orders.

        Returns:
            {'success' bool, 'errorCode': int, 'errorMessage': str,
             'responses': [{'success': bool, 'errorCode': int,
                            'errorMessage': str, 'id': int}]}
        """
        data = f'{{"orderIds":{order_ids}}}'
        return self.request("/order/cancel", data)
    
    # Haven't properly chararacterised the functionality of these;
    # need to update them.
    # P.S. The official API documentation is trash.

    def order_detail(self, order_ids: List[int]):
        data = f'{{"orderIds":{order_ids}}}'
        return self.request("/order/detail", data)

    def order_history(self, instrument: str, currency: str, limit: int, since_id: int):
        data = (f'{{"currency":"{currency}","instrument":"{instrument}",'
                f'"limit":{limit},"since":{since_id}}}')
        return self.request("/order/history", data)

    def order_open_history(self, instrument: str, currency: str, limit: int, since_id: int):
        data = (f'{{"currency":"{currency}","instrument":"{instrument}",'
                f'"limit":{limit},"since":{since_id}}}')
        return self.request("/order/open", data)

    def order_trade_history(self, instrument: str, currency: str, limit: int, since_id: int):
        data = (f'{{"currency":"{currency}","instrument":"{instrument}",'
                f'"limit":{limit},"since":{since_id}}}')
        return self.request("/order/trade/history", data)
    
    # UNTESTED
    def withdraw_crypto(self, amount: int, address: str, currency: str):
        data = f'{{"amount":{amount},"address":"{address}","currency":"{currency}"}}'
        return self.request("/fundtransfer/withdrawCrypto", data)
    
    # UNTESTED
    def withdraw_eft(self, account_name: str, account_number: str, bank_name: str,
                     bsb_number: str, amount: int, currency: str):
        data = (f'{{"accountName":"{account_name}","accountNumber":"{account_number}",'
                f'"bankName":"{bank_name}","bsbNumber":"{bsb_number}",'
                f'"amount":{amount},"currency":"{currency}"}}')
        return self.request("/fundtransfer/withdrawEFT", data)

    def transfer_history(self):
        return self.request("/fundtransfer/history")

