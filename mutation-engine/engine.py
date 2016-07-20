#!/usr/bin/env python
from classes.Utils import Utils
from logic.Linear import Linear
from primitives.block import block

# -----------------------------------------------------------------------------
#
# -----------------------------------------------------------------------------

grammar = Utils.read_grammar("./grammars/packet.json")
grammar = block(grammar)

for iteration in Linear(grammar).run():
    if iteration:
        print "".join(iteration)
