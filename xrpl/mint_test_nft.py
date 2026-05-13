from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountInfo
from xrpl.utils import drops_to_xrp

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"

WALLET_ADDRESS = "rEGJ6hV22uvEA5dKaoJkLLAWaarDedSTkt"
WALLET_SEED = "sEdSQnpFZdXPaaFtGSvo6zZRvoHFuxQ"

client = JsonRpcClient(JSON_RPC_URL)

wallet = Wallet.from_seed(WALLET_SEED)

acct_info = AccountInfo(
    account=WALLET_ADDRESS,
    ledger_index="validated"
)

response = client.request(acct_info)

balance_drops = response.result["account_data"]["Balance"]
balance_xrp = drops_to_xrp(balance_drops)

print("XRPL TEST WALLET")
print("----------------")
print(f"Address: {WALLET_ADDRESS}")
print(f"Balance: {balance_xrp} XRP")
