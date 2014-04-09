__author__ = 'Sarper'

from multinomial import *
import pydecode.hyper as ph
from collections import namedtuple


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


class RuleSpan(namedtuple("RuleSpan", ["lhs", "start_index", "end_index"])):
    def __str__(self):
        return "({}, {}, {})".format(self.lhs, self.start_index,
                                     self.end_index)


class Parser:

    def __init__(self, table_of_multinomials, terminals):

        self.multinomials = table_of_multinomials
        self.terminals = terminals

    def build_potentials(self, rule):

        return self.multinomials[rule.lhs].log_prob(rule)

    def get_unary_rules(self):

        for lhs in self.multinomials:
            for rule in self.multinomials[lhs]:
                if rule.unary:
                    yield rule

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
                    for nonterminal in list(self.multinomials) + ["S"]:
                        edgelist = []
                        for rule in self.multinomials[nonterminal]:
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
        weights = ph.Potentials(sentence_graph).build(self.build_potentials)
        path = ph.best_path(sentence_graph, weights)
        for edge in path.edges:
            print edge.label, self.build_potentials(edge.label)

    def parse_file(self, input_file):
        with open(input_file) as f:
            for sentence in f:
                self.parse(sentence)


def main():

    table_of_multinomials, terminals = read_counts('replaced_cfg.counts')
    parser = Parser(table_of_multinomials, terminals)
    parser.parse_file('sentence.dat')


if __name__ == "__main__":
    main()
