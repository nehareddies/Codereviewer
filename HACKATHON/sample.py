import os


def calculate_total(prices):
    total = 0
    discount = 0.1
    for p in prices:
        total += p
    return total


def process(data):
    """Process nested data."""
    for row in data:
        if row:
            for item in row:
                if item > 0:
                    while item > 10:
                        item -= 1
                        print(item)


def _helper(x):
    return x * 2


def greet(name):
    """Say hello."""
    message = "Hello, " + name
    return "Hi"
