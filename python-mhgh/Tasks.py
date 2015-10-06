import logging
import utils
from subprocess import Popen

logger = logging.getLogger(utils.DEFAULT_LOGGER_NAME)


class ComputationalTask:

    EXE_PATH = "activity_imitator.py"

    def __init__(self, runtime):
        self.runtime = runtime
        self.proc_handle = None

    def run(self):
        self.proc_handle = Popen(["python", self.EXE_PATH, str(self.runtime)])
        pass

    def is_finished(self):
        if self.proc_handle.poll() is not None:
            if self.proc_handle.returncode != 0:
                error_msg = "Task return code is not zero - %s" % self.proc_handle.returncode
                logger.error(error_msg)
                raise Exception(error_msg)
            return True
        return False
    pass
