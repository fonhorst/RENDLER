import json
import logging
import utils
from subprocess import Popen

logger = logging.getLogger(utils.DEFAULT_LOGGER_NAME)


class ComputationalTask:

    EXE_PATH = "activity_imitator.py"

    def __init__(self, task):
        # Task instance in json format
        self.task = task
        self.proc_handle = None

    def run(self):
        runtime = self.task['runtime']
        ## TODO: hack for debug
        runtime = 5
        self.proc_handle = Popen(["python", self.EXE_PATH, str(runtime)])
        pass

    def is_finished(self):
        if self.proc_handle.poll() is not None:
            if self.proc_handle.returncode != 0:
                error_msg = "Task return code is not zero - %s" % self.proc_handle.returncode
                logger.error(error_msg)
                raise Exception(error_msg)
            return True
        return False

    def task_repr(self):
        return json.dumps({'id': self.task['id']})

    pass
