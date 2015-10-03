import datetime
import logging


DEFAULT_LOGGER_NAME = "default_logger"

def get_time_label():
    return datetime.datetime.now().strftime("[%Y-%m-%d_%H-%M-%s]")

def configureLogger(time_label, is_executor=False):
    logger = logging.getLogger(DEFAULT_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    if is_executor:
        fh = logging.FileHandler(str(time_label) + '_executor' + '.log')
    else:
        fh = logging.FileHandler(str(time_label) + '_scheduler' + '.log')
    fh.setLevel(logging.INFO)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # create formatter and add it to the handlers
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter(u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)



