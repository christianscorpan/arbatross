def calc_volatility(price_history):
    if not price_history:
        return 0
    prices = [p["price"] for p in price_history]
    return (max(prices) - min(prices)) / min(prices) * 100 if min(prices) > 0 else 0

# Comment out for later use if needed
# def calc_diff(bin_price, slow_price):
#     return abs(bin_price - slow_price) / bin_price * 100
# def calc_latency(bin_time, slow_time):
#     return max(0, (slow_time - bin_time) * 1000)