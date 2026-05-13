from xrpl.wallet import generate_faucet_wallet
from xrpl.clients import JsonRpcClient

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"

client = JsonRpcClient(JSON_RPC_URL)

wallet = generate_faucet_wallet(client)

print("XRPL TEST WALLET CREATED")
print("------------------------")
print(f"Classic Address: {wallet.classic_address}")
print(f"Seed: {wallet.seed}")
