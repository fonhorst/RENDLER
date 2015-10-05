#!/usr/bin/env python

import json
import logging
import os
import signal
import sys
import time
from threading import Thread

try:
    from mesos.native import MesosExecutorDriver, MesosSchedulerDriver
    from mesos.interface import Executor, Scheduler
    from mesos.interface import mesos_pb2
except ImportError:
    from mesos import Executor, MesosExecutorDriver, MesosSchedulerDriver, Scheduler
    import mesos_pb2

import task_state
import utils
import messages

TASK_CPUS = 0.1
TASK_MEM = 32
SHUTDOWN_TIMEOUT = 30  # in seconds
LEADING_ZEROS_COUNT = 5  # appended to task ID to facilitate lexicographical order
TASK_ATTEMPTS = 5  # how many times a task is attempted

TEST_TASK_SUFFIX = "-test"


class ResourceInfo:
    def __init__(self, executor_id, slave_id):
        self.executor_id = executor_id
        self.slave_id = slave_id
    """
    :driver MesosSchedulerDriver
    """
    def askExecutor_Terminate(self, driver):

        eId = mesos_pb2.ExecutorID()
        eId.value = self.executor_id

        sId = mesos_pb2.SlaveID()
        sId.value = self.slave_id

        message = {"type": messages.SMT_TERMINATEEXECUTOR}
        o = json.dumps(message)
        logger.info("Tryna to kill eID: %s sID: %s" % (eId, sId))
        d = driver.sendFrameworkMessage(eId, sId, o)
        logger.info("-- %s" % (d))
        pass

    def askExecutor_ExecuteWFTask(self, driver, task_as_str):
        raise NotImplementedError()

    def askExecutor_StartStageIn(self, driver, task_as_str):
        raise NotImplementedError()
# See the Mesos Framework Development Guide:
# http://mesos.apache.org/documentation/latest/app-framework-development-guide

class TestScheduler(Scheduler):
    def __init__(self, testExecutor):
        logger.info("RENDLER")
        logger.info("=======")

        self.testExecutor  = testExecutor

        self.required_resources_number = 2
        # task_id => ResourceInfo map
        self.active_resources = {}

        ## running info
        self.shuttingDown = False
        self.tasksCreated = 0
        #self.viewed_slaves = set()
        self._driver = None

    def setDriver(self, driver):
        self._driver = driver
        pass

    def registered(self, driver, frameworkId, masterInfo):
        logger.info("Registered with framework ID [%s]" % frameworkId.value)

    def makeTaskPrototype(self, offer):
        task = mesos_pb2.TaskInfo()
        tid = self.tasksCreated
        self.tasksCreated += 1
        task.task_id.value = str(tid).zfill(LEADING_ZEROS_COUNT)
        task.slave_id.value = offer.slave_id.value
        cpus = task.resources.add()
        cpus.name = "cpus"
        cpus.type = mesos_pb2.Value.SCALAR
        cpus.scalar.value = TASK_CPUS
        mem = task.resources.add()
        mem.name = "mem"
        mem.type = mesos_pb2.Value.SCALAR
        mem.scalar.value = TASK_MEM
        return task

    def makeTestTask(self, text, offer):
        task = self.makeTaskPrototype(offer)
        task.name = "test task %s" % task.task_id.value
        task.task_id.value += TEST_TASK_SUFFIX
        task.executor.MergeFrom(self.testExecutor)
        task.executor.executor_id.value = "%s_%s_%s" % (self.testExecutor.executor_id.value,
                                                        offer.hostname, self.tasksCreated)
        task.data = str(text)
        return task

    def resourceOffers(self, driver, offers):

        for offer in offers:
            logger.info("Got resource offer [%s]" % offer.id.value)

            if self.shuttingDown:
                logger.info("Shutting down: declining offer on [%s]" % offer.hostname)
                driver.declineOffer(offer.id)
                continue

            self._try_to_form_pool(offer, driver)

            if self._is_pool_formed():
                logger.info("Pool is full. Terminate it")
                for task_id, rinfo in self.active_resources.items():
                    rinfo.askExecutor_Terminate(driver)
                #self._terminate_pool()

    def statusUpdate(self, driver, update):
        stateName = task_state.nameFor[update.state]
        logger.info("Task [%s] is in state [%s]" % (update.task_id.value, stateName))

    def frameworkMessage(self, driver, executorId, slaveId, message):
        o = json.loads(message)
        logger.info("Message: " + str(slaveId) + " " + str(executorId) + " " + str(o))

        if o["type"] == messages.EMT_READYTOWORK:
           # confirm resource as active
           rinfo = ResourceInfo(executorId.value, slaveId.value)
           self.active_resources[executorId.value] = rinfo

    """
    This function tries to form resource pool.
    if resources are enough it returns true
    """
    def _try_to_form_pool(self, offer, driver):
        if len(self.active_resources) < self.required_resources_number:
            logger.info("Accepting offer on [%s]" % offer.hostname)
            logger.info("Now we have [%s/%s]" % (len(self.active_resources), self.required_resources_number))
            task = self.makeTestTask("test_for_" + str(offer.hostname), offer)
            driver.launchTasks(offer.id, [task])
            # add the resource to pool
            self.active_resources[task.executor.executor_id.value] = None
        else:
            logger.info("Declining offer on [%s]" % offer.hostname)
            logger.info("We already have [%s/%s]" % (len(self.active_resources), self.required_resources_number))
            driver.declineOffer(offer.id)
            pass

    def _is_pool_formed(self):
        if len(self.active_resources) < self.required_resources_number:
            return False
        return all((rinfo is not None for task_id, rinfo in self.active_resources.items()))

    def _terminate_pool(self):
        for task_id, rinfo in self.active_resources.items():
            rinfo.askExecutor_Terminate(self._driver)
        pass

    pass


def hard_shutdown():
    driver.stop()

def graceful_shutdown(signal, frame):
    hard_shutdown()

#
# Execution entry point:
#
if __name__ == "__main__":

    time_label = utils.get_time_label()
    utils.configureLogger(time_label=time_label)
    logger = logging.getLogger(utils.DEFAULT_LOGGER_NAME)

    if len(sys.argv) < 2:
        print "Usage: %s mesosMasterUrl" % sys.argv[0]
        sys.exit(1)

    mesosMasterUrl = sys.argv[1]

    # baseURI = "/home/vagrant/hostfiles"
    baseURI = "/home/vagrant/devfiles"
    suffixURI = "python-mhgh"
    uris = [ "test_executor.py",
             "results.py",
             "messages.py",
             "task_state.py",
             "utils.py"]
    uris = [os.path.join(baseURI, suffixURI, uri) for uri in uris]


    testExecutor = mesos_pb2.ExecutorInfo()
    testExecutor.executor_id.value = "test-executor"
    testExecutor.command.value = "python test_executor.py " + str(time_label)

    for uri in uris:
        uri_proto = testExecutor.command.uris.add()
        uri_proto.value = uri
        uri_proto.extract = False

    testExecutor.name = "TestExecutor"

    framework = mesos_pb2.FrameworkInfo()
    framework.user = "" # Have Mesos fill in the current user.
    framework.name = "TestScheduler"
    framework.hostname = "192.168.92.5"


    rendler = TestScheduler(testExecutor)

    driver = MesosSchedulerDriver(rendler, framework, mesosMasterUrl)
    rendler.setDriver(driver)

    # driver.run() blocks; we run it in a separate thread
    def run_driver_async():
        status = 0 if driver.run() == mesos_pb2.DRIVER_STOPPED else 1
        driver.stop()
        sys.exit(status)
    framework_thread = Thread(target = run_driver_async, args = ())
    framework_thread.start()

    print "(Listening for Ctrl-C)"
    signal.signal(signal.SIGINT, graceful_shutdown)
    while framework_thread.is_alive():
        time.sleep(1)

    logging.info("Goodbye!")
    sys.exit(0)
