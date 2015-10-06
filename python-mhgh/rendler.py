#!/usr/bin/env python
from collections import deque

import logging
import os
import signal
import sys
import threading
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
from environment import Utility

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

        self.eId = mesos_pb2.ExecutorID()
        self.eId.value = self.executor_id
        self.sId = mesos_pb2.SlaveID()
        self.sId.value = self.slave_id
    """
    :driver MesosSchedulerDriver
    """
    def askExecutor_Terminate(self, driver):
        message = messages.create_message(messages.SMT_TERMINATEEXECUTOR)
        logger.info("Tryna to kill eID: %s sID: %s" % (self.eId, self.sId))
        d = driver.sendFrameworkMessage(self.eId, self.sId, message)
        pass

    def askExecutor_RunTask(self, driver, task):
        message = messages.create_message(messages.SMT_RUNTASK, task.json_repr())
        logger.info("Running Task %s on eID: %s sID: %s" % (task.id, self.eId, self.sId))
        d = driver.sendFrameworkMessage(self.eId, self.sId, message)
        pass

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


        self.workflow = Utility.Utility.readWorkflow("Montage_25.xml",
                                                     "Workflow", "00",
                                                     deadline=1000, is_head=True)

        logger.info("Wf job count %s" % self.workflow.get_task_count())

        self.finished_tasks = set([self.workflow.head_task.id])
        self.running_tasks = set()

    def setDriver(self, driver):
        self._driver = driver
        pass

    def registered(self, driver, frameworkId, masterInfo):
        logger.info("Registered with framework ID [%s]" % frameworkId.value)

        def run_scheduler_loop():
            logger.info("Scheduler loop is active")
            pool_has_been_formed = False
            execution_process_started = False
            while not self.shuttingDown:

                if pool_has_been_formed:
                    if not execution_process_started:
                        logger.info("Try to start execution process")
                        self.start_execution_process(driver)
                        execution_process_started = True
                        pass
                    pass
                elif self._is_pool_formed():
                    logger.info("Pool has been formed")
                    pool_has_been_formed = True
                    pass

                # -1 - we don't need to account a head_task
                logger.info("Tasks running %s " % (len(self.running_tasks)))
                logger.info("Tasks finished %s/%s " % (len(self.finished_tasks) - 1, self.workflow.get_task_count()))

                if self.workflow.get_task_count() == len(self.finished_tasks) - 1:
                    logger.info("Workload completed. Shutting down...")
                    hard_shutdown()

                time.sleep(2)
            logger.info("Scheduler loop is stopped")
            pass

        thread = threading.Thread(target=run_scheduler_loop)
        thread.start()
        pass

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
        pass

    def statusUpdate(self, driver, update):
        stateName = task_state.nameFor[update.state]
        logger.info("Task [%s] is in state [%s]" % (update.task_id.value, stateName))

    def frameworkMessage(self, driver, executorId, slaveId, message):
        logger.info("Message: " + str(slaveId) + " " + str(executorId) + " " + str(message))

        message_type = messages.message_type(message)

        if message_type == messages.EMT_READYTOWORK:
           # confirm resource as active
           rinfo = ResourceInfo(executorId.value, slaveId.value)
           self.active_resources[executorId.value] = rinfo

        if message_type == messages.EMT_TASKFINISHED:
            rinfo = self.active_resources[executorId.value]

            finished_task_id = messages.message_body(message)['id']
            self.finished_tasks.add(finished_task_id )
            tasks = self.workflow.ready_to_run_tasks(self.finished_tasks, self.running_tasks)
            self.running_tasks.remove(finished_task_id)
            if len(tasks) > 0:
                task = tasks[0]
                rinfo.askExecutor_RunTask(driver, task)
                self.running_tasks.add(task.id)


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

    def start_execution_process(self, driver):
        tasks = deque(self.workflow.ready_to_run_tasks(self.finished_tasks, self.running_tasks))
        logger.info("Ready to run tasks %s" % (tasks))
        if len(tasks) == 0:
            return
        for executor_Id, rinfo in self.active_resources.items():
            task = tasks.popleft()
            rinfo.askExecutor_RunTask(driver, task)
            self.running_tasks.add(task.id)

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
             "tasks.py",
             "activity_imitator.py",
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
