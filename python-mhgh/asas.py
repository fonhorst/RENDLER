from environment import Utility

if __name__ == "__main__":
     workflow = Utility.Utility.readWorkflow("Montage_5.xml",
                                                     "Workflow", "00",
                                                     deadline=1000, is_head=True)

     for task in workflow.get_all_unique_tasks():
         st = task.json_repr()
