from config import public_key, private_key
from rest_interface import RESTInterface

interface = RESTInterface(public_key, private_key)
print(interface.balances())
