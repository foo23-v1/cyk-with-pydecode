__author__ = 'Sarper'

from multinomial import *


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
                    self.unary_rule_with_nonterm[terms[2]][(terms[3])] = count

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

    def parse(self,input_file):

def main():
    counts = Counts()
    counts.read_counts('replaced_cfg.counts')
    table_of_multinomials = TableOfMultinomial()
    for nonterm in counts.nonterm.iterkeys():
        nonterm_counts = \
            counts.binary_rule_with_nonterm.get(nonterm, {}).copy()
        nonterm_counts.update(counts.unary_rule_with_nonterm.get(nonterm, {}))
        table_of_multinomials.create(nonterm, nonterm_counts)


if __name__ == "__main__":
    main()
