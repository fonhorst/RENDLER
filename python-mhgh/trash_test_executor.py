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
import json
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


import results
import utils
import messages



class TestExecutor(Executor):

    def registered(self, driver, executorInfo, frameworkInfo, slaveInfo):
      logger.info("TestExecutor registered on hostname: " + str(slaveInfo.hostname))

    def reregistered(self, driver, slaveInfo):
      logger.info("TestExecutor reregistered")

    def disconnected(self, driver):
      logger.info("TestExecutor disconnected")

    def launchTask(self, driver, task):
        def run_task():
            time.sleep(10)

        thread = threading.Thread(target=run_task)
        thread.start()
        logger.info("task started")

    def killTask(self, driver, taskId):
        self.shutdown(self, driver)

    def frameworkMessage(self, driver, message):
      logger("Ignoring framework message: %s" % message)

    def shutdown(self, driver):
      logger.info("Shutting down")
      sys.exit(0)

    def error(self, error, message):
      pass

if __name__ == "__main__":

    if len(sys.argv) > 1:
        time_label = sys.argv[1]
    else:
        time_label = utils.get_time_label()

    utils.configureLogger(time_label = time_label, is_executor=True)
    logger = logging.getLogger(utils.DEFAULT_LOGGER_NAME)

    logger.info("Starting Launching Executor (LE)")
    driver = MesosExecutorDriver(TestExecutor())
    sys.exit(0 if driver.run() == mesos_pb2.DRIVER_STOPPED else 1)
