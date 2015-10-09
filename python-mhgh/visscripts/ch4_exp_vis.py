import datetime
from matplotlib import pyplot
import time


# def seconds_to_norm_time(runtime_seconds):
#     exec_time = runtime_seconds * 200
#     # hours
#     hours = exec_time // 3600
#     # remaining seconds
#     s = exec_time - (hours * 3600)
#     # minutes
#     minutes = s // 60
#     # remaining seconds
#     seconds = s - (minutes * 60)
#     # total time
#     print '%s:%s:%s' % (hours, minutes, seconds)
from matplotlib.ticker import FuncFormatter


def experiment_seconds_to_norm_time(runtime_seconds):
    exec_seconds = runtime_seconds * 100
    return exec_seconds
    #td = datetime.timedelta(seconds=exec_seconds)
    #return td


def convert_time(lst):
    return [experiment_seconds_to_norm_time(secs) for secs in lst]


def plot_makespan():
    pyplot.xlabel("Time of fault")
    pyplot.ylabel("Final makespan")

    ## first graph
    pyplot.plot(x, sbsm_9_to_6, '-rD', label="9 - 6")
    pyplot.plot(x, sbsm_9_to_6_recon, '-gD', label="9 - 6 reconfigured")
    #
    ## second graph
    pyplot.plot(x, sbsm_9_to_3, '-mD', label="9 - 3")
    pyplot.plot(x, sbsm_9_to_3_recon, '-bD', label="9 - 3 reconfigured")
    ## plot deadline
    pyplot.plot(x, convert_time([110, 110, 110, 110, 110, 110]), "-y")
    pyplot.legend()

    def timespan(x, pos):
        'The two args are the value and tick position'
        return str(datetime.timedelta(seconds=x))

    formatter = FuncFormatter(timespan)
    pyplot.gca().yaxis.set_major_formatter(formatter)


def plot_quality():
    pyplot.xlabel("Time of fault")
    pyplot.ylabel("Ensemble size")

    # first quality graph
    pyplot.plot(x, quality_sbsm_9_to_6, '-rD', label="9 - 6")
    pyplot.plot(x, quality_sbsm_9_to_6_recon, '-gD', label="9 - 6 reconfigured")

    # second quality graph
    pyplot.plot(x, quality_sbsm_9_to_3, '-mD', label="9 - 3")
    pyplot.plot(x, quality_sbsm_9_to_3_recon, '-bD', label="9 - 3 reconfigured")
    pyplot.ylim(0, 25)
    pyplot.legend(loc=4)


if __name__ == "__main__":

    # in % - completness of the wf when a fail occurs
    x = [0, 10, 25, 50, 75, 100]

    # withOUT wf reconfiguring in seconds
    sbsm_9_to_6 = [138, 138, 138, 128, 108, 102]
    quality_sbsm_9_to_6 = [20, 20, 20, 20, 20, 20]
    # WITH wf reconfiguring
    sbsm_9_to_6_recon = [108, 108, 107, 106, 106, 102]
    quality_sbsm_9_to_6_recon = [14, 14, 13, 14, 20, 20]

    # withOUT wf reconfiguring
    sbsm_9_to_3 = [248, 242, 242, 212, 182, 102]
    quality_sbsm_9_to_3 = [20, 20, 20, 20, 20, 20]
    # WITH wf reconfiguring
    sbsm_9_to_3_recon = [108, 108, 107, 106, 106, 102]
    quality_sbsm_9_to_3_recon = [4, 4, 5, 7, 13, 20]

    sbsm_9_to_6 = convert_time(sbsm_9_to_6)
    sbsm_9_to_6_recon = convert_time(sbsm_9_to_6_recon)
    sbsm_9_to_3 = convert_time(sbsm_9_to_3)
    sbsm_9_to_3_recon = convert_time(sbsm_9_to_3_recon)

    pyplot.figure(figsize=(10, 10))
    pyplot.grid()


    # plot_makespan()
    plot_quality()



    pyplot.show()

    pass
