from matplotlib import pyplot

if __name__ == "__main__":

    # in % - completness of the wf when a fail occurs
    x = [0, 10, 25, 50, 75, 100]

    # withOUT wf reconfiguring
    sbsm_9_to_6 = [2.18, 2.18, 2.18, 2.08, 1.48, 1.42]
    quality_sbsm_9_to_6 = [20, 20, 20, 20, 20, 20]
    # WITH wf reconfiguring
    sbsm_9_to_6_recon = [1.48, 1.48, 1.47, 1.46, 1.46, 1.42]
    quality_sbsm_9_to_6_recon = [6, 5, 5, 7, 18, 20]

    # withOUT wf reconfiguring
    sbsm_9_to_3 = [4.08, 4.02, 4.02, 3.32, 3.02, 1.42]
    quality_sbsm_9_to_3 = [20, 20, 20, 20, 20, 20]
    # WITH wf reconfiguring
    sbsm_9_to_3_recon = [1.48, 1.48, 1.47, 1.46, 1.46, 1.42]
    quality_sbsm_9_to_3_recon = [6, 3, 3, 6, 16, 20]


    pyplot.figure(figsize=(10, 10))
    pyplot.grid()

    pyplot.xlabel("Time of fault")
    pyplot.ylabel("Final makespan")

    ## first graph
    # pyplot.plot(x, sbsm_9_to_6, '-rD', label="9 - 6")
    # pyplot.plot(x, sbsm_9_to_6_recon, '-gD', label="9 - 6 reconfigured")
    #
    ## second graph
    # pyplot.plot(x, sbsm_9_to_3, '-mD', label="9 - 3")
    # pyplot.plot(x, sbsm_9_to_3_recon, '-bD', label="9 - 3 reconfigured")

    # first quality graph
    pyplot.plot(x, quality_sbsm_9_to_6, '-rD', label="9 - 6")
    pyplot.plot(x, quality_sbsm_9_to_6_recon, '-gD', label="9 - 6 reconfigured")

    # second quality graph
    pyplot.plot(x, quality_sbsm_9_to_3, '-mD', label="9 - 3")
    pyplot.plot(x, quality_sbsm_9_to_3_recon, '-bD', label="9 - 3 reconfigured")
    pyplot.ylim(0, 25)


    pyplot.legend(loc=4)
    pyplot.show()

    pass
