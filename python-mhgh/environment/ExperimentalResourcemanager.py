
from ResourceManager import ResourceManager
from BaseElements import Node, Resource


class ExperimentResourceManager(ResourceManager):

    def setVMParameter(self, rules_list):
        """
        Established farm_capacity and max resource_capacity for each resource
        """
        if len(self.resources) != len(rules_list):
            print("Resources count not equal to rules_list length")
        for res, rule in zip(self.resources, rules_list):
            res.farm_capacity = rule[0]
            res.max_resource_capacity = rule[1]

    def __init__(self, resources):
        self.resources = resources
        self.resources_map = {res.name: res for res in self.resources}
        self._name_to_node = None

    # # TODO: fix problem with id
    def node(self, node):
        if isinstance(node, Node):
            result = [nd for nd in self.resources_map[node.resource.name].nodes if nd.name == node.name]
        else:
            name = node
            result = [nd for nd in self.get_nodes() if nd.name == name]

        if len(result) == 0:
            return None
        return result[0]

    def resource(self, resource):
        return self.res_by_id(resource)

    ##get all resources in the system
    def get_resources(self):
        return self.resources

    def get_live_resources(self):
        resources = self.get_resources()
        result = set()
        for res in resources:
            if res.state != 'down':
                result.add(res)
        return result

    def get_live_nodes(self):
        resources = [res for res in self.get_resources() if res.state != 'down']
        result = set()
        for resource in resources:
            for node in resource.nodes:
                if node.state != "down":
                    result.add(node)
        return result

    def get_all_nodes(self):
        result = set()
        for res in self.resources:
            for node in res.nodes:
                result.add(node)
        return result

    def change_performance(self, node, performance):
        ##TODO: rethink it
        self.resources[node.resource][node].flops = performance

    def byName(self, name):
        if self._name_to_node is None:
            self._name_to_node = {n.name: n for n in self.get_nodes()}
        return self._name_to_node.get(name, None)

    def res_by_id(self, id):
        name = id.name if isinstance(id, Resource)else id
        return self.resources_map[name]

    def get_res_by_name(self, name):
        """
        find resource from resource list by name
        """
        for res in self.resources:
            if res.name == name:
                return res
        return None

    def get_node_by_name(self, name):
        """
        find node in all resources by name
        """
        for res in self.resources:
            for node in res.nodes:
                if node.name == name:
                    return node
        return None
