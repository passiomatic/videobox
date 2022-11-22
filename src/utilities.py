from datetime import datetime, date, timedelta

def scale_between(value, minAllowed, maxAllowed, min, max):
    return (maxAllowed - minAllowed) * (value - min) / (max - min) + minAllowed