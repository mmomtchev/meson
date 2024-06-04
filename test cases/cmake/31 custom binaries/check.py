#!/usr/bin/env python

import sys
import ast

with open(sys.argv[1]) as log:
    lines = log.readlines()
    assert(len(lines) > 4)
    parsed = [ast.literal_eval(l) for l in lines]
    flat = [item for row in parsed for item in row]
    assert('--version' in flat)
    assert('-C' in flat)
    assert('-t' in flat)
    assert('build.ninja' in flat)
    assert('ninja2.py' in flat[-1])
