"""Functions used to measure the execution time of a wrapped function"""
from collections import Counter
from functools import wraps
from time import time

from tabulate import tabulate

number_of_calls = Counter()
total_time_per_function = Counter()


def timing(function_to_time):
    """
    Annotation which can be used to time the execution time of a wrapped function.
    It stores the number of invocation and the total execution time internally.
    """

    @wraps(function_to_time)
    def wrapper(*args, **kwargs):
        start = time()
        result = function_to_time(*args, **kwargs)
        end = time()
        number_of_calls[function_to_time.__name__] += 1
        total_time_per_function[function_to_time.__name__] += end - start
        return result

    return wrapper


def print_timing_results():
    """
    Prints out the internally stored function calls with their respective execution times
    """
    headers = ["Function", "# calls", " total time", "time per call"]
    rows = []
    for func in number_of_calls.keys():
        time_per_call = total_time_per_function[func] / number_of_calls[func]
        rows.append([func, number_of_calls[func], total_time_per_function[func], time_per_call])
    print("\nTiming results: ")
    print(tabulate(rows, headers))
