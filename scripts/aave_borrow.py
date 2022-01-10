from scripts.helpful_scripts import get_account, LOCAL_BLOCKCHAIN_ENVIRONMENTS
from brownie import config, network, interface
from scripts.get_weth import get_weth
from web3 import Web3


def get_lending_pool():
    print(config["networks"][network.show_active()]["lending_pool_addresses_provider"])
    lending_pool_addresses_provider = interface.ILendingPoolAddressesProvider(
        config["networks"][network.show_active()]["lending_pool_addresses_provider"]
    )
    lending_pool_address = lending_pool_addresses_provider.getLendingPool()
    lending_pool = interface.ILendingPool(lending_pool_address)
    return lending_pool


def approve_erc20(amount, spender, erc20_address, account):
    print("Approving ERC20 token...")
    erc20 = interface.IERC20(erc20_address)
    tx = erc20.approve(spender, amount, {"from": account})
    tx.wait(1)
    print("Approved ERC20 token!")
    return tx


def get_borrowable_data(lending_pool, account):
    (
        total_collateral_eth,
        total_debt_eth,
        available_borrow_eth,
        current_liquidation_threshold,
        ltv,
        health_factor,
    ) = lending_pool.getUserAccountData(account.address, {"from": account})
    available_borrow_eth = Web3.fromWei(available_borrow_eth, "ether")
    total_collateral_eth = Web3.fromWei(total_collateral_eth, "ether")
    total_debt_eth = Web3.fromWei(total_debt_eth, "ether")
    print(f"You have {total_collateral_eth} worth of ETH deposited in your account.")
    print(f"You have {total_debt_eth} worth of ETH borrowed.")
    print(f"You have {available_borrow_eth} worth of ETH available to borrow.")
    return (float(available_borrow_eth), float(total_debt_eth))


def get_asset_price(price_feed_address):
    dai_eth_price_feed = interface.AggregatorV3Interface(price_feed_address)
    latest_price = dai_eth_price_feed.latestRoundData()[1]
    converted_latest_price = Web3.fromWei(latest_price, "ether")
    print(f"The DAI/ETH price is {converted_latest_price}")
    return float(latest_price)


def repay_all(amount, lending_pool, account):
    approve_erc20(
        Web3.toWei(amount, "ether"),
        lending_pool.address,
        config["networks"][network.show_active()]["dai_token"],
        account,
    )
    repay_tx = lending_pool.repay(
        config["networks"][network.show_active()]["dai_token"],
        amount,
        1,
        account.address,
        {"from": account},
    )
    repay_tx.wait(1)


def main():
    account = get_account()
    erc20_address = config["networks"][network.show_active()]["weth_token"]
    if network.show_active() in LOCAL_BLOCKCHAIN_ENVIRONMENTS:
        # Get some Weth
        get_weth()
    # Now we'll work with the AAVE Lending Pool
    # To interact we need the ABI and the Address, as ever
    lending_pool = get_lending_pool()
    # We have to approve sending our ERC20 tokens
    amount = Web3.toWei(0.1, "ether")  # 0.1 WETH
    approve_erc20(amount, lending_pool.address, erc20_address, account)
    # Now we can deposit!
    tx = lending_pool.deposit(
        erc20_address, amount, account.address, 0, {"from": account}
    )  # Referral codes don't work anymore
    tx.wait(1)
    print("Deposited 0.1 WETH")
    # How much can we now borrow?
    borrowable_eth, total_debt = get_borrowable_data(lending_pool, account)
    print("Let's borrow some DAI!")
    dai_eth_price = get_asset_price(
        config["networks"][network.show_active()]["dai_eth_price_feed"]
    )
    amount_dai_to_borrow = (1 / dai_eth_price) * (borrowable_eth * 0.95)
    # borrowable_eth -> borrowable_dai * 0.95
    dai_to_borrow_wei = Web3.toWei(amount_dai_to_borrow, "ether")
    print(f"We are going to borrow {dai_to_borrow_wei} DAI")
    dai_address = config["networks"][network.show_active()]["dai_token"]
    borrow_tx = lending_pool.borrow(
        dai_address,
        dai_to_borrow_wei,
        1,  # Use a stable interest rate
        0,
        account.address,
        {"from": account},
    )
    borrow_tx.wait(1)
    print("Borrowed DAI!")
    get_borrowable_data(lending_pool, account)
    repay_all(amount, lending_pool, account)
    print("You just deposited, borrowed, and repayed with AAVE, Brownie and Chainlink")
