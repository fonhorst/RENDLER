import sys
import time

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Not Enough Args")
        sys.exit(2)

    runtime = float(sys.argv[1])
    time.sleep(runtime)
    sys.exit(0)
