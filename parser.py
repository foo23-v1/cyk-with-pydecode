__author__ = 'Sarper'

from multinomial import *
import pydecode.hyper as ph
from collections import namedtuple
from itertools import izip
import json

def read_counts(count_file):
    """
    Reads counts from count_file
    """
    nonterm = {}
    term = {}
    binary_rule_with_nt = {}
    unary_rule_with_nt = {}

    with open(count_file) as f:
        for line in f:
            terms = line.strip().split()
            if terms[1] == 'NONTERMINAL':
                nonterm[terms[2]] = int(terms[0])

            elif terms[1] == 'UNARYRULE':
                count = int(terms[0])
                term.setdefault(terms[3], 0)
                term[terms[3]] += count
                unary_rule_with_nt.setdefault(terms[2], {})
                unary_rule_with_nt[terms[2]][Rule(terms[2], (terms[3],))] =\
                    count

            elif terms[1] == 'BINARYRULE':
                count = int(terms[0])
                binary_rule_with_nt.setdefault(terms[2], {})
                binary_rule_with_nt[terms[2]][
                    Rule(terms[2], (terms[3], terms[4]))] = count

    table_of_multinomials = TableOfMultinomial()
    for nonterm in nonterm.iterkeys():
        nonterm_counts = \
            binary_rule_with_nt.get(nonterm, {}).copy()
        nonterm_counts.update(unary_rule_with_nt.get(nonterm, {}))
        table_of_multinomials.create(nonterm, nonterm_counts)

    return table_of_multinomials, term


class Rule(namedtuple("Rule", ["lhs", "rhs"])):

    @property
    def unary(self):
        return len(self.rhs) == 1

    @property
    def rhs_first(self):
        return self.rhs[0]

    @property
    def rhs_second(self):
        return self.rhs[1]

    def __hash__(self):
        if self.unary:
            return hash((self.lhs, self.rhs_first))
        return hash((self.lhs, self.rhs_first, self.rhs_second))

class RuleSpan(namedtuple("RuleSpan", ["lhs", "start_index", "end_index"])):
    def __str__(self):
        return "({}, {}, {})".format(self.lhs, self.start_index,
                                     self.end_index)


class Dummy:

    def __getitem__(self, item):
        print item
        return 0


class Parser:

    def __init__(self, table_of_multinomials, terminals):

        self.table_of_multinomials = table_of_multinomials
        self.terminals = terminals

    def build_potentials(self, rule):

        return self.table_of_multinomials[rule.lhs].log_prob(rule)

    def build_potential_map(self, sentence_graph):

        return {edge.id: self.build_potentials(edge.label)
                for edge in sentence_graph.edges}

    def get_unary_rules(self):

        for lhs in self.table_of_multinomials:
            for rule in self.table_of_multinomials[lhs]:
                if rule.unary:
                    yield rule

    def max_min_objective(self, sentence_graph, words):
        d = [float("-inf")] * len(sentence_graph.nodes)
        terminal_node_labels = [RuleSpan(words[i], i+1, i+1) for i in xrange(len(words))]
        for node in sentence_graph.nodes:
            if node.label in terminal_node_labels:
                d[node.id] = float("inf")
            for edge in sentence_graph.nodes[node.id].edges:
                if len(edge.tail) < 2:
                    d[node.id] = max(min(d[edge.tail[0].id], self.build_potentials(edge.label)), d[node.id])
                else:
                    d[node.id] = max(min(d[edge.tail[0].id], d[edge.tail[1].id], self.build_potentials(edge.label))
                                     , d[node.id])
        return d[len(d)-1]

    def prune_hypergraph(self, sentence_graph, threshold):

        graph_filter = ph.BoolPotentials(sentence_graph).from_vector(
            [0 if self.build_potentials(edge.label) < threshold else 1 for edge in sentence_graph.edges])
        projection = ph.project(sentence_graph, graph_filter)
        new_graph = projection.range_hypergraph

        return new_graph

    def get_edge_list(self, gold_parse, edge_set):
        if len(gold_parse) == 3:
            r = Rule(gold_parse[0], (gold_parse[1][0], gold_parse[2][0]))
            edge_set.add(r)
            self.get_edge_list(gold_parse[1], edge_set)
            self.get_edge_list(gold_parse[2], edge_set)

        elif(len(gold_parse)==2):
            if gold_parse[1] not in self.terminals or self.terminals[gold_parse[1]] < 5:
                r = Rule(gold_parse[0], ('_RARE_',))
            else:
                r = Rule(gold_parse[0], (gold_parse[1],))
            edge_set.add(r)

    def build_hypergraph(self, sentence):

        words = sentence.strip().split(" ")
        n = len(words)
        nodes = {}
        for i, word in enumerate(words):
            if word not in self.terminals or self.terminals[word] < 5:
                words[i] = '_RARE_'

        sentence_graph = ph.Hypergraph()
        with sentence_graph.builder() as b:
            for i, word in enumerate(words, start=1):
                relevant_rules = (rule for rule in self.get_unary_rules()
                                  if rule.rhs_first == word)
                r = RuleSpan(word, i, i)
                nodes[r] = b.add_node(label=r)
                for rule in relevant_rules:
                    nodes[RuleSpan(rule.lhs, i, i)] = b.add_node(
                        [([nodes[RuleSpan(rule.rhs_first, i, i)]], rule)],
                        label=RuleSpan(rule.lhs, i, i))
            for l in xrange(1, n):
                for i in xrange(1, n-l+1):
                    j = i+l
                    for nonterminal in list(self.table_of_multinomials) + ["S"]:
                        edgelist = []
                        for rule in self.table_of_multinomials[nonterminal]:
                            if rule.unary:
                                continue
                            for s in xrange(i, j):
                                rule_span1 = RuleSpan(rule.rhs_first, i, s)
                                rule_span2 = RuleSpan(rule.rhs_second, s+1, j)
                                if rule_span1 in nodes.keys()\
                                        and rule_span2 in nodes.keys():
                                    edgelist.append((
                                        [nodes[rule_span1],
                                         nodes[rule_span2]],
                                        rule))
                        if edgelist:
                            rs = RuleSpan(nonterminal, i, j)
                            nodes[rs] = b.add_node(edgelist, label=rs)

        return words, sentence_graph

    def best_path(self, sentence_graph):

        pv = self.build_potential_map(sentence_graph)
        weights = ph.Potentials(sentence_graph).from_map(pv)
        path = ph.best_path(sentence_graph, weights)

        return path

    def parse(self, sentence):
        words = sentence.strip().split(" ")
        n = len(words)
        nodes = {}
        for i, word in enumerate(words):
            if word not in self.terminals or self.terminals[word] < 5:
                words[i] = '_RARE_'

        sentence_graph = ph.Hypergraph()
        with sentence_graph.builder() as b:
            for i, word in enumerate(words, start=1):
                relevant_rules = (rule for rule in self.get_unary_rules()
                                  if rule.rhs_first == word)
                r = RuleSpan(word, i, i)
                nodes[r] = b.add_node(label=r)
                for rule in relevant_rules:
                    nodes[RuleSpan(rule.lhs, i, i)] = b.add_node(
                        [([nodes[RuleSpan(rule.rhs_first, i, i)]], rule)],
                        label=RuleSpan(rule.lhs, i, i))
            for l in xrange(1, n):
                for i in xrange(1, n-l+1):
                    j = i+l
                    for nonterminal in list(self.table_of_multinomials):
                        edgelist = []
                        for rule in self.table_of_multinomials[nonterminal]:
                            if rule.unary:
                                continue
                            for s in xrange(i, j):
                                rule_span1 = RuleSpan(rule.rhs_first, i, s)
                                rule_span2 = RuleSpan(rule.rhs_second, s+1, j)
                                if rule_span1 in nodes.keys()\
                                        and rule_span2 in nodes.keys():
                                    edgelist.append((
                                        [nodes[rule_span1],
                                         nodes[rule_span2]],
                                        rule))
                        if edgelist:
                            rs = RuleSpan(nonterminal, i, j)
                            nodes[rs] = b.add_node(edgelist, label=rs)

        pv = self.build_potential_map(sentence_graph)
        weights = ph.Potentials(sentence_graph).from_map(pv)
        path = ph.best_path(sentence_graph, weights)
        for edge in path.edges:
            print edge.label, self.build_potentials(edge.label)


        print len(sentence_graph.edges), len(sentence_graph.nodes)
        max_min_weight = self.max_min_objective(sentence_graph, words)
        print max_min_weight
        prunned_graph = self.prune_hypergraph(sentence_graph, max_min_weight)
        print len(prunned_graph.edges), len(prunned_graph.nodes)
        # for node in prunned_graph.nodes:
        #     print node.label
        # for edge in prunned_graph.edges:
        #     print edge.label

    def print_path(self,root_node, path, sentence):

        if not root_node.edges:
            return sentence.strip().split(" ")[root_node.label.start_index-1]
        edge_in_path = [edge for edge in path if edge.id in imap(lambda x: x.id, root_node.edges)][0]
        tail_nodes = edge_in_path.tail
        if len(tail_nodes)==2:
            left_child, right_child = tail_nodes
            return [root_node.label.lhs, self.print_path(left_child, path, sentence), self.print_path(right_child, path, sentence)]
        else:
            child = tail_nodes[0]
            return [root_node.label.lhs, self.print_path(child,path,sentence)]

    def parse_file(self, input_file, key_file):
        counter = 0

        with open(input_file) as f, open(key_file) as k,\
                open('cky_results.txt', 'w') as cky,\
                open('max_min_results.txt', 'w') as mm,\
                open('prunned_gold_edges.txt', 'w') as pge,\
                open('statistics.txt', 'w') as st:
            print >>st, "Original#Nodes", "Original#EDGEs", "AfterPrunning#", "AfterPrunning#",\
                "%NodesPrunned", "%EdgesPrunned"
            for sentence, gold_parse_json in izip(f, k):
                counter += 1
                print counter
                gold_parse = json.loads(gold_parse_json)
                gold_edge_list = set()
                self.get_edge_list(gold_parse, gold_edge_list)
                words, sentence_graph = self.build_hypergraph(sentence)
                path = self.best_path(sentence_graph)
                result_tree = self.print_path(path.nodes[len(path.nodes)-1], path, sentence)
                print >> cky, json.dumps(result_tree)

                max_min_weight = self.max_min_objective(sentence_graph, words)
                print >>pge, max_min_weight
                print >>pge, json.dumps([(edge, self.build_potentials(edge))
                                         for edge in gold_edge_list if self.build_potentials(edge) < max_min_weight])
                prunned_graph = self.prune_hypergraph(sentence_graph, max_min_weight)
                cky_node_count = len(sentence_graph.nodes)
                cky_edge_count = len(sentence_graph.edges)
                pr_node_count = len(prunned_graph.nodes)
                pr_edge_count = len(prunned_graph.edges)
                print >>st, cky_node_count, cky_edge_count, pr_node_count, pr_edge_count, \
                    (cky_node_count-pr_node_count)*100.0/cky_node_count, \
                    (cky_edge_count-pr_edge_count)*100.0/cky_edge_count
                path = self.best_path(prunned_graph)
                result_tree = self.print_path(path.nodes[len(path.nodes)-1], path, sentence)
                print >> mm, json.dumps(result_tree)

def main():

    table_of_multinomials, terminals = read_counts('replaced_cfg.counts')
    parser = Parser(table_of_multinomials, terminals)
    parser.parse_file('parse_dev.dat', 'parse_dev.key')


if __name__ == "__main__":
    main()
