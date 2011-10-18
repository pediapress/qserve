#! /usr/bin/env py.test

import pytest
import time
import gevent
from qs.misc import call_in_loop


def throw_error():
    raise RuntimeError("as requested")


def test_iterate_error():
    c = call_in_loop(0.05, throw_error)
    stime = time.time()
    c.iterate()
    needed = time.time() - stime
    assert needed > 0.05


def test_fail_and_restart():
    lst = []

    def doit():
        lst.append(len(lst))
        print "doit", lst
        if len(lst) == 5:
            raise RuntimeError("size is 5")
        elif len(lst) == 10:
            raise gevent.GreenletExit("done")

    c = call_in_loop(0.001, doit)
    pytest.raises(gevent.GreenletExit, c)
