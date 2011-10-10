#! /usr/bin/env py.test

import cPickle
from qs import jobs


def test_job_defaults():
    j1 = jobs.job("render")
    assert j1.ttl == 3600
    assert j1.priority == 0


def test_job_pickle():
    j1 = jobs.job("render", payload=(1, 2, 3), priority=5, jobid=11, timeout=100, ttl=20)
    j2 = cPickle.loads(cPickle.dumps(j1))

    assert j2.channel == "render"
    assert j2.payload == (1, 2, 3)
    assert j2.priority == 5
    assert j2.jobid == 11
    assert j2.timeout == j1.timeout
    assert j2.ttl == 20


def test_workq_pickle():
    w = jobs.workq()
    w.pushjob(jobs.job("render1"))
    w.pushjob(jobs.job("render2"))
    w2 = cPickle.loads(cPickle.dumps(w))
    print w.__dict__
    print w2.__dict__
    assert w.__dict__ == w2.__dict__
