__author__ = 'Sarper'

from multinomial import *
import pydecode.hyper as ph


class Counts:

    def __init__(self):
        self.unary = {}
        self.binary = {}
        self.nonterm = {}
        self.term = {}
        self.binary_rule_with_nonterm = {}
        self.unary_rule_with_nonterm = {}

    def read_counts(self, count_file):
        """
        Reads counts from count_file
        """

        with open(count_file) as f:
            for line in f:
                terms = line.strip().split()
                if terms[1] == 'NONTERMINAL':
                    self.nonterm.setdefault(terms[2], 0)
                    self.nonterm[terms[2]] = int(terms[0])

                elif terms[1] == 'UNARYRULE':
                    count = int(terms[0])
                    key = (terms[2], terms[3])
                    self.unary.setdefault(key, 0)
                    self.term.setdefault(terms[3], 0)
                    self.unary[key] = count
                    self.term[terms[3]] += count
                    self.unary_rule_with_nonterm.setdefault(terms[2], {})
                    self.unary_rule_with_nonterm[terms[2]][(terms[3],)] = count

                elif terms[1] == 'BINARYRULE':
                    count = int(terms[0])
                    key = (terms[2], terms[3], terms[4])
                    self.binary.setdefault(key, 0)
                    self.binary[key] = count
                    self.binary_rule_with_nonterm.setdefault(terms[2], {})
                    self.binary_rule_with_nonterm[terms[2]][
                        (terms[3], terms[4])] = count


class Parser:

    def __init__(self, table_of_multinomials, counts):
        self.table_of_multinomials = table_of_multinomials
        self.counts = counts

    def build_potentials(self, edge):
        return self.table_of_multinomials[edge[0]].log_prob(edge[1:])



    def parse(self, sentence):
        words = sentence.strip().split(" ")
        n = len(words)
        nodes = {}
        for i, word in enumerate(words):
            if word not in self.counts.term or self.counts.term[word] < 5:
                words[i] = '_RARE_'
        sentence_graph = ph.Hypergraph()
        with sentence_graph.builder() as b:
            for i, word in enumerate(words, start=1):
                relevant_rules = (rule for rule in self.counts.unary.iterkeys()
                                  if rule[1] == word)
                nodes[(word, i, i)] = b.add_node(label=(word))
                for rule in relevant_rules:
                    #node_str = "%s:%d:%d" % (rule[0], i, i)
                    #edge_str = "%s:%s" % (rule[0], rule[1])
                    #print node_str, edge_str
                    nodes[(rule[0], i, i)] = b.add_node(
                        [([nodes[(rule[1], i, i)]], (rule[0], rule[1]))],
                        label=(rule[0], i, i))
            for l in xrange(1, n):
                for i in xrange(1, n-l+1):
                    j = i+l
                    for nonterminal in\
                            self.counts.binary_rule_with_nonterm.iterkeys():
                        edgelist = []
                        for rule in \
                                self.counts.binary_rule_with_nonterm[nonterminal].iterkeys():
                            for s in xrange(i, j):
                                if (rule[0], i, s) in nodes.keys()\
                                        and (rule[1], s+1, j) in nodes.keys():
                                    edgelist.append((
                                        [nodes[(rule[0], i, s)],
                                         nodes[(rule[1], s+1, j)]],
                                        (nonterminal, rule[0], rule[1])))
                        if edgelist:
                            nodes[(nonterminal, i, j)] = b.add_node(edgelist, label=(nonterminal, i, j))
        weights = ph.Potentials(sentence_graph).build(self.build_potentials)
        path = ph.best_path(sentence_graph, weights)
        # for edge in path.edges:
        #     print edge.label, self.build_potentials(edge.label)
    def parse_file(self, input_file):
        count = 1
        with open(input_file) as f:
            for sentence in f:
                self.parse(sentence)
                print count
                count += 1


def main():

    counts = Counts()
    counts.read_counts('replaced_cfg.counts')
    table_of_multinomials = TableOfMultinomial()
    for nonterm in counts.nonterm.iterkeys():
        nonterm_counts = \
            counts.binary_rule_with_nonterm.get(nonterm, {}).copy()
        nonterm_counts.update(counts.unary_rule_with_nonterm.get(nonterm, {}))
        table_of_multinomials.create(nonterm, nonterm_counts)
    parser = Parser(table_of_multinomials, counts)
    parser.parse_file('parse_dev.dat')



if __name__ == "__main__":
    main()
