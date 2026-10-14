import json


def load_orders(path):
    raw = open(path).read()
    orders = json.loads(raw)
    count = len(orders)
    return orders


def apply_discounts(orders, vip_names):
    """Apply discounts to each order."""
    results = []
    for order in orders:
        if order["total"] > 0:
            if order["customer"] in vip_names:
                for item in order["items"]:
                    if item["price"] > 100:
                        try:
                            item["price"] = item["price"] * 0.9
                        except KeyError:
                            pass
        results.append(order)
    return results


async def send_receipt(order):
    message = "Thanks for your order"
    tracking = order.get("tracking")
    print(order["customer"])


def make_counter():
    """Return a counter function."""
    total = 0

    def increment():
        nonlocal total
        total += 1
        return total

    return increment


def _internal_check(value):
    unused_flag = True
    _ignored = 5
    return value > 0


class OrderReport:
    def summary(self, orders):
        lines = []
        for order in orders:
            lines.append(order["customer"])
        return lines
