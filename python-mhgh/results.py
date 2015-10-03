import json


class Result(object):
	def __repr__(self):
		return json.dumps(self.__dict__, sort_keys = True)

class TestResult(Result):
    def __init__(self, test_str, text):
        self.test_str = test_str
        self.text = text
