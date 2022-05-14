import datetime
from decimal import Decimal


def format_time(timestamp):
    return datetime.datetime.fromtimestamp(timestamp)


def average_age(timestamp, genesis_time):
    the_timestamp = datetime.datetime.fromtimestamp(timestamp)
    genesis_timestamp = datetime.datetime.fromtimestamp(genesis_time)
    difference = the_timestamp - genesis_timestamp
    difference_in_days = Decimal(difference.total_seconds()) / Decimal(86400)
    return f"{difference_in_days:.2f}"
