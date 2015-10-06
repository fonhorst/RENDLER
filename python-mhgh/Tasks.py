import json
import logging
import time
import utils
from subprocess import Popen

logger = logging.getLogger(utils.DEFAULT_LOGGER_NAME)


class ComputationalTask:

    EXE_PATH = "activity_imitator.py"

    def __init__(self, task):
        # Task instance in json format
        self.task = task
        self.proc_handle = None

        self.real_start_time = None
        self.real_end_time = None

    def run(self):
        runtime = self.task['runtime']
        # TODO: hack for debug
        runtime = runtime / 200
        self.proc_handle = Popen(["python", self.EXE_PATH, str(runtime)])
        self.real_start_time = time.time()
        pass

    def is_finished(self):
        if self.proc_handle.poll() is not None:
            if self.proc_handle.returncode != 0:
                error_msg = "Task return code is not zero - %s" % self.proc_handle.returncode
                logger.error(error_msg)
                raise Exception(error_msg)
            self.real_end_time = time.time() if self.real_end_time is None else self.real_end_time
            return True
        return False

    def killTask(self):
        self.proc_handle.kill()
        pass

    def task_repr(self):
        return json.dumps({'id': self.task['id'],
                           'real_start_time': self.real_start_time,
                           'real_end_time': self.real_end_time})

    pass
