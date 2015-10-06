import json

EMT_READYTOWORK = "ReadyToWork"
EMT_TASKFINISHED = "TaskFinished"


# Scheduler message type
SMT_TERMINATEEXECUTOR = "TerminateExecutor"
SMT_RUNTASK = "RunTask"
SMT_POISONPILL = "PoisonPill"


def create_message(type, body=""):
    message = {"type": type, "body": body}
    o = json.dumps(message)
    return o


def message_type(message):
    o = json.loads(message)
    return o["type"]


def message_body(message):
    o = json.loads(message)
    body = json.loads(o["body"])
    return body