from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import NFTokenMint
from xrpl.transaction import submit_and_wait

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"

WALLET_SEED = "sEdSQnpFZdXPaaFtGSvo6zZRvoHFuxQ"

client = JsonRpcClient(JSON_RPC_URL)

wallet = Wallet.from_seed(WALLET_SEED)

nft_mint = NFTokenMint(
    account=wallet.address,
    uri="68747470733A2F2F707572706177732E63612F6D657461646174612F6261696C65792E6A736F6E",
    flags=8,
    transfer_fee=0,
    nftoken_taxon=0,
)

print("Minting NFT on XRPL Testnet...")
print("--------------------------------")
print("Metadata URI: https://purpaws.ca/metadata/bailey.json")

response = submit_and_wait(
    transaction=nft_mint,
    client=client,
    wallet=wallet
)

print("NFT MINT COMPLETE")
print("------------------")
print(response.result)
