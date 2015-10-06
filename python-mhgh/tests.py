import time
import tasks


def test_ctask():
    task = tasks.ComputationalTask(10)
    task.run()
    while not task.is_finished():
        print("Not ready yet")
        time.sleep(1)
    print("OK")

if __name__ == "__main__":
    test_ctask()
