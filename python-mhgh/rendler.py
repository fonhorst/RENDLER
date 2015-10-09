#!/usr/bin/env python
from collections import deque

import logging
import os
import signal
import sys
import threading
import time
from threading import Thread
import datetime

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
from environment.ResourceManager import ScheduleItem, Schedule
from environment.ExperimentalResourceManager import ExperimentResourceManager
from environment.ExperimentalEstimator import TransferCalcExperimentEstimator
from environment.DSimpleHeft import run_heft
from environment.BaseElements import Resource


TASK_CPUS = 0.1
TASK_MEM = 32
SHUTDOWN_TIMEOUT = 30  # in seconds
LEADING_ZEROS_COUNT = 5  # appended to task ID to facilitate lexicographical order
TASK_ATTEMPTS = 5  # how many times a task is attempted

TEST_TASK_SUFFIX = "-test"

MB_100_CHANNEL = 13*1024*1024

from environment.BaseElements import Node, SoftItem

class ResourceInfo:

    # executor runs currently a task
    BUSY = "busy"
    # executor do nothing
    FREE = "free"
    # offer was accepted, by executor hasn't sent an answer back yet
    NOT_CONFIRMED = "not_confirmed"
    # failed
    DEAD = "dead"

    def __init__(self, executor_id, slave_id, task_id):
        self.executor_id = executor_id
        self.slave_id = slave_id
        self.task_id = task_id
        self.name = self.executor_id

        self.eId = mesos_pb2.ExecutorID()
        self.eId.value = self.executor_id
        self.sId = mesos_pb2.SlaveID()
        self.sId.value = self.slave_id
        self.tId = mesos_pb2.TaskID()
        self.tId.value = self.task_id

        self.state = ResourceInfo.NOT_CONFIRMED

    """
    :return Node instance
    """
    def construct_node_desc(self):
        # here should some kind real flops value
        # resource should be set later
        node = Node(self.name, None, [SoftItem.ANY_SOFT], flops=1)
        node.state = Node.Down if self.state == ResourceInfo.DEAD else Node.Unknown
        logger.info("name %s - state %s" % (self.name, node.state))
        return node

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

    def askExecutor_PoisonPill(self, driver):
        message = messages.create_message(messages.SMT_POISONPILL)
        logger.info("Sending Poison Pill to eID: %s sID: %s" % (self.eId, self.sId))
        d = driver.sendFrameworkMessage(self.eId, self.sId, message)
        pass

    def askExecutor_StartStageIn(self, driver, task_as_str):
        raise NotImplementedError()

    def killExecutor(self, driver):
        logger.info("Killing executor %s" % self.executor_id)
        d = driver.killTask(self.tId)
        pass


    def change_state(self, new_state):
        self.state = new_state

    def is_free(self):
        return self.state == ResourceInfo.FREE
# See the Mesos Framework Development Guide:
# http://mesos.apache.org/documentation/latest/app-framework-development-guide

class TestScheduler(Scheduler):
    def __init__(self, testExecutor):
        logger.info("RENDLER")
        logger.info("=======")

        self.testExecutor  = testExecutor

        self.rlock = threading.RLock()
        self.required_resources_number = 9
        # task_id => ResourceInfo map
        self.active_resources = {}

        ## running info
        self.shuttingDown = False
        self.tasksCreated = 0
        #self.viewed_slaves = set()
        self._driver = None


        self.workflow = Utility.Utility.readWorkflow("swanbsm20.xml",
                                                     "Workflow", "00",
                                                     deadline=1000, is_head=True)

        self.workflow_2 = Utility.Utility.readWorkflow("swanbsm5.xml",
                                                     "Workflow", "00",
                                                     deadline=1000, is_head=True)

        logger.info("Wf job count %s" % self.workflow.get_task_count())

        self.current_schedule = Schedule.empty_schedule()
        self.execution_process_start_time = None

        # dirty hack for quick solution
        self.fail_has_been_generated = False

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
                self.rlock.acquire()
                if pool_has_been_formed:
                    if not execution_process_started:
                        logger.info("Try to start execution process")
                        self.start_execution_process(driver)
                        execution_process_started = True
                        pass

                    if execution_process_started:
                        # special service function
                        # whose goal is to simulate a situation of lost nodes
                        self.check_for_nodes_fault()
                        pass

                    pass
                elif self._is_pool_formed():
                    logger.info("Pool has been formed")

                    self.construct_scheduling_tools()

                    pool_has_been_formed = True
                    pass

                # -1 - we don't need to account a head_task
                finished_tasks = len(self.current_schedule.finished_node_item_pairs())
                executing_tasks = len(self.current_schedule.executing_node_item_pairs())
                logger.info("Tasks running %s " % (executing_tasks))
                logger.info("Tasks finished %s/%s " % (finished_tasks,
                                                       self.workflow.get_task_count()))

                if self.workflow.get_task_count() == finished_tasks:
                    end_execution_time = time.time()
                    start = datetime.datetime.fromtimestamp(self.execution_process_start_time)
                    end  = datetime.datetime.fromtimestamp(end_execution_time)
                    logger.info("Workload completed. Shutting down...")
                    logger.info("Start execution time: %s" % (start))
                    logger.info("End execution time: %s" % (end))
                    logger.info("Execution time: %s" % ((end - start)))

                    Utility.Utility.validate_dynamic_schedule(self.workflow, self.current_schedule)

                    hard_shutdown()

                self.rlock.release()

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

        if stateName == "TASK_LOST":
            logger.info("YESYESYES")
            logger.info("YESYESYES")
            logger.info("YESYESYES")
            logger.info("YESYESYES")

        pass

    def offerRescinded(self, driver, offerId):
       logger.info("Offer rescinded" % (offerId))
       pass


    def frameworkMessage(self, driver, executorId, slaveId, message):
        logger.info("Message: " + str(slaveId) + " " + str(executorId) + " " + str(message))

        self.rlock.acquire()

        if executorId.value not in self.active_resources:
            logger.info("Exceutor %s hasn't been recognized as registered. Dropping message. Possibly that executor was deleted" % (executorId.value))
            return

        if self.active_resources[executorId.value].state == ResourceInfo.DEAD:
            logger.info("Executor %s marked as a dead. Dropping message" % (executorId.value))
            return

        message_type = messages.message_type(message)

        if message_type == messages.EMT_READYTOWORK:
           # confirm resource as active
           self.active_resources[executorId.value].change_state(ResourceInfo.FREE)

        if message_type == messages.EMT_TASKFINISHED:
            # id
            # real_start_time
            # real_end_time
            rinfo = self.active_resources[executorId.value]

            body = messages.message_body(message)
            finished_task_id = body['id']
            real_start_time = body['real_start_time']
            real_end_time = body['real_end_time']

            # self.current_schedule.change_state_byId(finished_task_id, ScheduleItem.FINISHED)

            node, item = self.current_schedule.place_non_failed(finished_task_id)
            logger.info("Item state: %s" % item.state)
            item.real_start_time = real_start_time
            item.real_end_time = real_end_time
            item.state = ScheduleItem.FINISHED
            rinfo.change_state(ResourceInfo.FREE)

            logger.info("TaskFinished: %s" % self.current_schedule)

            self.run_next_tasks(driver)

            # tasks = self.workflow.ready_to_run_tasks(self.finished_tasks, self.running_tasks)
            # self.running_tasks.remove(finished_task_id)
            # if len(tasks) > 0:
            #     task = tasks[0]
            #     rinfo.askExecutor_RunTask(driver, task)
            #     self.running_tasks.add(task.id)
        self.rlock.release()


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
            self.active_resources[task.executor.executor_id.value] = ResourceInfo(task.executor.executor_id.value,
                                                                                  task.slave_id.value,
                                                                                  task.task_id.value)
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

        # make scheduling
        logger.info("Building Schedule")
        heft_schedule = run_heft(self.workflow, self.rm, self.estimator)
        Utility.Utility.validate_static_schedule(self.workflow, heft_schedule)
        logger.info("HEFT makespan: " + str(Utility.Utility.makespan(heft_schedule)))

        self.execution_process_start_time = time.time()

        self.current_schedule = heft_schedule
        self.run_next_tasks(driver)

    def run_next_tasks(self, driver):
        # in this case, this funcion will return only first level tasks
        # a task can be started if:
        # 1) all dependecies - predeseccors tasks - are finished
        # 2) all needed data(explicitly controlled) are on the node
        # 3) the chosen node are free of other workload (e.g. tasks)

        # check all dependencies
        schedule_pairs = self.current_schedule.next_to_run(self.workflow)

        # check data dependecies
        # TODO:

        ready_to_run_pairs = schedule_pairs

        # check availability of nodes
        # ready_to_run_pairs = [(node, item) for (node, item) in schedule_pairs
        #                       if self.active_resources[node.name].is_free()]

        logger.info("Run tasks: %s" % [item.job.id for node, item in ready_to_run_pairs])
        for node, item in ready_to_run_pairs:
            if not self.active_resources[node.name].is_free():
                continue
            rinfo = self.active_resources[node.name]
            task = item.job
            rinfo.askExecutor_RunTask(driver, task)

            self.current_schedule.change_state(item.job, ScheduleItem.EXECUTING)
            rinfo.change_state(ResourceInfo.BUSY)
        pass


    """
    Builds rsource manager and estimator to be needed for scheduling
    """
    def construct_scheduling_tools(self):

        nodes = [rinfo.construct_node_desc() for executor_id, rinfo in self.active_resources.items()]

        resources = [Resource(node.name, nodes=[node]) for node in nodes]

        rm = ExperimentResourceManager(resources)
        estimator = TransferCalcExperimentEstimator(ideal_flops=1,
                                                    reliability=1.0,
                                                    transfer_nodes=MB_100_CHANNEL,
                                                    transfer_blades=100)
        self.rm = rm
        self.estimator = estimator

        return rm, estimator

        pass

    def check_for_nodes_fault(self):
        finished_task_count = len(self.current_schedule.finished_node_item_pairs())
        all_task_count  = len(self.workflow.get_all_unique_tasks())
        # if finished_task_count >= all_task_count*0.5:

        end_execution_time = time.time()
        start = datetime.datetime.fromtimestamp(self.execution_process_start_time)
        end  = datetime.datetime.fromtimestamp(end_execution_time)
        diff = (end - start).seconds

        # if finished_task_count >= (all_task_count * 0.75) and not self.fail_has_been_generated:

        # bsm20 - 9 res - 1.42 min - deadline: 1.5 min
        # diff = [10, 25, 50, 75]
        # bsm10 - 9 res - 1.14 min - deadline: 1.2 min
        # diff - [8, 20, 40, 60]

        if diff >=10 and not self.fail_has_been_generated:
            logger.info("Tring to kill")
            self.fail_has_been_generated = True
            resources = list(sorted(self.active_resources.keys()))
            # resources_to_be_killed = resources[:int(len(resources)/2)]
            resources_to_be_killed = resources[:3]
            # resources_to_be_killed = [resources[0]]
            for executor_id in resources_to_be_killed:
                rinfo = self.active_resources[executor_id]
                rinfo.killExecutor(driver)
                rinfo.change_state(ResourceInfo.DEAD)
                #rinfo.askExecutor_PoisonPill(driver)

            # now we can count that resources has been gone. We need:
            # 1) update rm
            # 2) update schedule, marks part of tasks as a failed
            # 3) relaunch scheduling and remake schedule
            # 3) check if the new solution is within deadline border
            # 4) if it is not, try to generate new solution with reduced count tasks
            # 5) repeat 3 - 5 until either succesful is found or there is no option any more
            # 6) if solution has been found apply, other raise exception about deadline violation

            # return
            # raise NotImplementedError

            # update rm and estimator
            self.construct_scheduling_tools()

            # remove all planned tasks from the current schedule
            # and marks failed tasks
            new_mapping = {}
            for (node, items) in self.current_schedule.mapping.items():
                new_node = self.rm.get_node_by_name(node.name)
                new_mapping[new_node] = []
                for item in items:
                    if new_node.state == Node.Down and item.state == ScheduleItem.EXECUTING:
                        ## Note! in the old schedule (self.current_schedule) this tasks will be marked as failed too
                        item.state = ScheduleItem.FAILED
                    if item.state != ScheduleItem.UNSTARTED:
                        new_mapping[new_node].append(item)
            clean_schedule = Schedule(new_mapping)

            logger.info("===RESCHEDULING PHASE===")
            logger.info("Current schedule: %s" % self.current_schedule)
            logger.info("Clean schedule: %s" % clean_schedule)

            ## replace current with reduced one (workflow-2) to save time
            # self.workflow = self.workflow_2

            st = time.time()
            not_calculated_bsm, not_calculated_swan = self.wf_struct_opt(schedule=self.current_schedule, level=-14)
            end = time.time()
            logger.info("TIME to adapt executio process: %s" % (end - st))
            # not_calculated_bsm, not_calculated_swan = [], []

            # resume execution process
            heft_schedule = run_heft(self.workflow, self.rm, self.estimator, fixed_schedule=clean_schedule)

            # make it finished
            for id in not_calculated_bsm:
                node, item = heft_schedule.place_non_failed(id)
                item.state = ScheduleItem.FINISHED

            for id in not_calculated_swan:
                node, item = heft_schedule.place_non_failed(id)
                item.state = ScheduleItem.FINISHED
            #

            logger.info("NOT_CALCULATED_BSM: %s" % len(not_calculated_bsm))
            logger.info("New Heft Schedule: %s" % heft_schedule)


            logger.info("New HEFT makespan: " + str(Utility.Utility.makespan(heft_schedule)))
            logger.info("===END RESCHEDULING PHASE===")
            self.current_schedule = heft_schedule
            self.run_next_tasks(self._driver)

        pass


    def wf_struct_opt(self, schedule, level):
        # minimal quality
        executed_bsms = []
        # 1+ level
        executing_bsms = []
        # second_level
        executed_swans = []
        # third level
        executing_swans = []
        # forth level
        not_started_swans = []
        for (node, items) in schedule.mapping.items():
            for item in items:
                soft = list(item.job.soft_reqs)
                if len(soft) > 0 and soft[0] == "bsm":
                    if item.state == ScheduleItem.FINISHED:
                        executed_bsms.append(item)
                    if item.state == ScheduleItem.EXECUTING:
                        executing_bsms.append(item)
                if len(soft) > 0 and soft[0] == "swan":
                    if item.state == ScheduleItem.FINISHED:
                        executed_swans.append(item)
                    if item.state == ScheduleItem.EXECUTING:
                        executing_swans.append(item)
                    if item.state == ScheduleItem.FAILED or item.state == ScheduleItem.UNSTARTED:
                        not_started_swans.append(item)
            pass

        logger.info("Executed bsms- %s" % len(executed_bsms))
        logger.info("Executing bsms - %s" % len(executing_bsms))
        logger.info("Executed swans - %s" % len(executed_swans))
        logger.info("Executing swans - %s" % len(executing_swans))
        logger.info("Not started swans - %s" % len(not_started_swans))

        def find_swan(item):
            for p in item.job.parents:
                soft = list(p.soft_reqs)
                if len(soft) > 0 and soft[0] == "swan":
                    return p

        def find_bsm(item):
            for p in item.job.children:
                soft = list(p.soft_reqs)
                if len(soft) > 0 and soft[0] == "bsm":
                    return p


        # get pairs of minimum available quality
        min_saved_swan = {}
        min_saved_bsm = {}
        for item in executed_bsms + executing_bsms:
            p = find_swan(item)
            min_saved_swan[p.id] = p
            min_saved_bsm[item.job.id] = item.job

        first_level_swanbsm = []
        for item in executed_bsms:
            p = find_swan(item)
            first_level_swanbsm.append((p, item.job))

        first_level_swanbsm_extended = []
        for item in executing_bsms:
            p = find_swan(item)
            first_level_swanbsm_extended.append((p, item.job))

        # get second level
        second_level_swan = {}
        second_level_bsm = {}
        second_level_swanbsm = []
        for item in executed_swans:
            if item.job.id not in min_saved_swan:
                c = find_bsm(item)
                # it's already executed
                #second_level_swan[item.job.id] = item.job
                second_level_bsm[c.id] = c
                second_level_swanbsm.append((item.job, c))


        # get third level
        third_level_swan = {}
        third_level_bsm = {}
        third_level_swanbsm = []
        for item in executing_swans:
            c = find_bsm(item)
            # it's already executing
            #third_level_swan[item.job.id] = item.job
            third_level_bsm[c.id] = c
            third_level_swanbsm.append((item.job, c))

        # get forth level
        forth_level_swan = {}
        forth_level_bsm = {}
        forth_level_swanbsm = []
        for item in not_started_swans:
            c = find_bsm(item)
            forth_level_swan[item.job.id] = item.job
            forth_level_bsm[c.id] = c
            # swan - bsm
            forth_level_swanbsm.append((item.job, c))

        #level = 2

        not_calculated_bsm = []
        not_calculated_swan = []

        # use percent of desired swan-bsm pairs. It will determine execution time
        if level < 0:
            swanbsm_count = -1*level
            swanbsm_pairs = first_level_swanbsm + first_level_swanbsm_extended + \
                            second_level_swanbsm + third_level_swanbsm + forth_level_swanbsm
            # if count of bsms that have been already calculated is bigger than we need
            # than we will use it
            swanbsm_count = len(first_level_swanbsm) if swanbsm_count < len(first_level_swanbsm) else swanbsm_count
            desired_pairs = swanbsm_pairs[:swanbsm_count]

            all_bsms = set(list(min_saved_bsm.keys()) + list(second_level_bsm.keys())
                           + list(third_level_bsm.keys()) + list(forth_level_bsm.keys()))
            all_swans = set(list(min_saved_swan.keys()) + list(second_level_swan.keys())
                            + list(third_level_swan.keys()) + list(forth_level_swan.keys()))

            desired_swans = [swan_task.id for swan_task, bsm_task in desired_pairs]
            logger.info("ALL SWANS %s " % all_swans)
            logger.info("DESIRED SWANS %s" % desired_swans)

            for swan_task, bsm_task in desired_pairs:
                all_bsms.remove(bsm_task.id)
                res = self.current_schedule.place_non_failed(swan_task.id)
                ## res is None == ScheduleItem.FAILED
                if res is None or res[1].state == ScheduleItem.UNSTARTED:
                    # all_swans doesn't contain executing or executed swans
                    all_swans.remove(swan_task.id)

            not_calculated_bsm = list(all_bsms)
            not_calculated_swan = list(all_swans)

        ## only first level stays
        if level == 0:
            not_calculated_bsm = list(second_level_bsm.keys()) + list(third_level_bsm.keys()) + list(forth_level_bsm.keys())
            not_calculated_swan = list(second_level_swan.keys()) + list(third_level_swan.keys()) + list(forth_level_swan.keys())

        ## first and second - half way
        # not_calculated_bsm = not_calculated_bsm[0:int(len(not_calculated_bsm)/2)] \
        #     if len(not_calculated_bsm) > 1 else not_calculated_bsm

        # not_calculated_swan = not_calculated_swan[0:int(len(not_calculated_swan)/2)] \
        #     if len(not_calculated_swan) > 1 else not_calculated_swan

        # first and second
        if level == 1:
            logger.info("First Level BSM: %s" % len(min_saved_bsm))
            logger.info("Second Level BSM: %s" % len(second_level_bsm))
            not_calculated_bsm = list(third_level_bsm.keys()) + list(forth_level_bsm.keys())
            not_calculated_swan = list(third_level_swan.keys()) + list(forth_level_swan.keys())

        # if (level < 1 and len(min_saved_bsm) == 0) and len(second_level_swan) > 0:
        #
        #     swan_keys = list(second_level_swan.keys())
        #     skey = swan_keys[0]
        #     swan_keys = swan_keys[1:] if len(swan_keys) > 1 else []



        # not_calculated_bsm =  swan_keys + list(third_level_bsm.keys()) + list(forth_level_bsm.keys())
        # not_calculated_swan = list(third_level_swan.keys()) + list(forth_level_swan.keys())

        #
        #
        #
        # first, second and third
        if level == 2 :
            logger.info("forth_level_swanbsm %s " % len(forth_level_swanbsm))

            not_calculated_bsm = list(forth_level_bsm.keys())
            not_calculated_swan = list(forth_level_swan.keys())
            #
            # not_calculated_bsm = [bsm.id for swan, bsm in forth_level_swanbsm[:3]]
            # not_calculated_swan = [swan.id for swan, bsm in forth_level_swanbsm[:3]]

        if level == 3:
            not_calculated_swan = []
            not_calculated_bsm = []

        # for id in not_calculated_bsm:
        #     task = self.workflow.byId(id)
        #     task.runtime = 0
        #
        # for id in not_calculated_swan:
        #     task = self.workflow.byId(id)
        #     task.runtime = 0

        return not_calculated_bsm, not_calculated_swan


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
    framework_thread = Thread(target=run_driver_async, args = ())
    framework_thread.start()

    print "(Listening for Ctrl-C)"
    signal.signal(signal.SIGINT, graceful_shutdown)
    while framework_thread.is_alive():
        time.sleep(1)

    logging.info("Goodbye!")
    sys.exit(0)
