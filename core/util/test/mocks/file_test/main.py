import os
import sys

# checks read and write permissions of linked files.
if __name__ == "__main__":
    try:
        with open("read.txt", "r") as f:
            print(f"file_test: got expected read result")
    except Exception as e:
        print(f"file_test: got unexpected exception {e}")
        sys.exit(1)
    try:
        with open("read.txt", "w") as f:
            f.write("READ")
        print("file_test: incorrectly allowed write")
        sys.exit(1)
    except Exception as e:
        print(f"file_test: got expected exception {e}")
    try:
        with open("write.txt", "w") as f:
            f.write("WRITE")
            print("file_test: got expected write result")
    except Exception as e:
        print(f"file_test: got unexpected exception {e}")
        sys.exit(1)
