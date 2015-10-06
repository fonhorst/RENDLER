#!/usr/bin/env python

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

import sys
import threading
import time


try:
    from mesos.native import MesosExecutorDriver, MesosSchedulerDriver
    from mesos.interface import Executor, Scheduler
    from mesos.interface import mesos_pb2
except ImportError:
    from mesos import Executor, MesosExecutorDriver, MesosSchedulerDriver, Scheduler
    import mesos_pb2

import utils
import messages
import tasks


class TestExecutor(Executor):

    def __init__(self):
        self._is_shutting_down = False
        self.runnig_task = None

    def registered(self, driver, executorInfo, frameworkInfo, slaveInfo):
      logger.info("TestExecutor registered on hostname: " + str(slaveInfo.hostname))

    def reregistered(self, driver, slaveInfo):
      logger.info("TestExecutor reregistered")

    def disconnected(self, driver):
      logger.info("TestExecutor disconnected")

    def launchTask(self, driver, task):
        def run_task():
            logger.info("Running main cycle %s" % task.task_id.value)
            update = mesos_pb2.TaskStatus()
            update.task_id.value = task.task_id.value
            update.state = mesos_pb2.TASK_RUNNING
            driver.sendStatusUpdate(update)

            #text = task.data
            #res = results.TestResult("Hello from task: " + str(task.task_id.value), text=text)
            #message = repr(res)
            #driver.sendFrameworkMessage(message)

            message = messages.create_message(messages.EMT_READYTOWORK)
            driver.sendFrameworkMessage(message)

            while(not self._is_shutting_down):
                # report about task if it is finished
                self.check_computations(driver)

                time.sleep(5)

            logger.info("Sending status update...")
            update = mesos_pb2.TaskStatus()
            update.task_id.value = task.task_id.value
            update.state = mesos_pb2.TASK_FINISHED
            driver.sendStatusUpdate(update)
            logger.info("Sent status update")
            return


        thread = threading.Thread(target=run_task)
        thread.start()
        pass

    def killTask(self, driver, taskId):
        self.shutdown(driver)

    def frameworkMessage(self, driver, message):
        #logger("Ignoring framework message: %s" % message)
        logger.info("Message received: %s" % message)
        message_type = messages.message_type(message)

        # finish
        if message_type == messages.SMT_TERMINATEEXECUTOR:
            logger.info("Termination signal received...")
            self.shutdown(driver)

        # run comp task
        if message_type == messages.SMT_RUNTASK:
            # here should be Task instance
            task = messages.message_body(message)
            logger.info("run task id: %s, runtime: %s" % (task['id'], task['runtime']))
            if self.runnig_task is not None:
                # TODO: make a special message to refuse to run
                logger.error("Alarm! Node is not empty")
                raise Exception("Node is not empty")
            self.runnig_task = tasks.ComputationalTask(task)
            ## spawn compute-intesive task
            self.runnig_task.run()

        pass

    def shutdown(self, driver):
      logger.info("Shutting down")
      self._is_shutting_down = True
      #sys.exit(0)

    def error(self, error, message):
      pass

    def check_computations(self, driver):
        if self.runnig_task is None:
            return False

        if not self.runnig_task.is_finished():
            return False

        message = messages.create_message(messages.EMT_TASKFINISHED, self.runnig_task.task_repr())
        driver.sendFrameworkMessage(message)

        self.runnig_task = None
        return True

if __name__ == "__main__":

    if len(sys.argv) > 1:
        time_label = sys.argv[1]
    else:
        time_label = utils.get_time_label()

    utils.configureLogger(time_label = time_label, is_executor=True)
    logger = logging.getLogger(utils.DEFAULT_LOGGER_NAME)

    logger.info("Starting Launching Executor (LE)")
    driver = MesosExecutorDriver(TestExecutor())
    exit_code = 0 if driver.run() == mesos_pb2.DRIVER_STOPPED else 1
    logger.info("Executor is finished")
    sys.exit(exit_code)
