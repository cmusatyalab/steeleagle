import pstats
from pstats import SortKey

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="cprofile reader")
    parser.add_argument(
        "-p", "--path", default="./drivers/olympe/driver_test.out", help="the path to workspace"
    )
    args = parser.parse_args()
    path = args.path
    p = pstats.Stats(path)
    p.sort_stats(SortKey.TIME).print_stats(10)
