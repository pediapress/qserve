#! /usr/bin/env py.test

import cPickle
from qs import jobs
import gevent


def pytest_funcarg__wq(request):
    return jobs.workq()


def loaddump(obj):
    return cPickle.loads(cPickle.dumps(obj))


def test_job_defaults():
    j1 = jobs.job("render")
    assert j1.ttl == 3600
    assert j1.priority == 0


def test_job_repr_unicode():
    r = repr(jobs.job("render", jobid=unichr(256)))
    assert isinstance(r, str)


def test_job_repr_none():
    repr(jobs.job("render"))


def test_job_repr_int():
    repr(jobs.job("render", jobid=41))


def test_job_pickle():
    j1 = jobs.job("render", payload=(1, 2, 3), priority=5, jobid=11, timeout=100, ttl=20)
    j2 = loaddump(j1)

    assert j2.channel == "render"
    assert j2.payload == (1, 2, 3)
    assert j2.priority == 5
    assert j2.jobid == 11
    assert j2.timeout == j1.timeout
    assert j2.ttl == 20
    assert j2.done == False


def test_job_unpickle_event():
    j = jobs.job("render")
    j = loaddump(j)
    assert not j.finish_event.is_set()

    j.done = True
    j = loaddump(j)
    assert j.finish_event.is_set()


def test_workq_pickle(wq):
    wq.pushjob(jobs.job("render1"))
    wq.pushjob(jobs.job("render2"))
    w2 = loaddump(wq)
    print wq.__dict__
    print w2.__dict__
    assert wq.__dict__ == w2.__dict__


def test_pushjob_automatic_jobid(wq):
    for x in range(1, 10):
        j = jobs.job("render", payload="hello")
        jid = wq.pushjob(j)
        assert (jid, j.jobid) == (x, x)


def test_pushjob_no_automatic_jobid(wq):
    for jobid in ["", "123", unichr(255), 0]:
        j = jobs.job("render", payload="hello", jobid=jobid)
        jid = wq.pushjob(j)
        assert (jid, j.jobid) == (jobid, jobid)


def test_pushjob_pop(wq):
    j1 = jobs.job("render", payload="hello")
    jid = wq.pushjob(j1)
    assert jid == 1
    assert j1.jobid == 1
    assert len(wq.channel2q["render"]) == 1
    assert len(wq.timeoutq) == 1

    j = wq.pop(["foo", "render", "bar"])
    assert j is j1

    g1 = gevent.spawn(wq.pop, ["render"])
    gevent.sleep(0)

    j2 = jobs.job("render", payload=" world")
    wq.pushjob(j2)
    g1.join()
    res = g1.get()
    assert res is j2


def test_stats(wq):
    joblst = [wq.push("render", payload=i) for i in range(10)]
    stats = wq.getstats()
    print "stats before", stats
    assert stats == {'count': 10, 'busy': {'render': 10}, 'channel2stat': {}, 'numjobs': 10}

    wq.killjobs(joblst[1:])

    stats = wq.getstats()
    print "stats after", stats
    assert stats == {'count': 10, 'busy': {'render': 1}, 'channel2stat': {'render': {'success': 0, 'killed': 9, 'timeout': 0, 'error': 0}}, 'numjobs': 10}
    print wq.waitjobs(joblst[1:])


def test_pop_does_preen(wq):
    jlist = [jobs.job("render", payload=i) for i in range(10)]
    for j in jlist:
        wq.pushjob(j)

    for j in jlist[:-1]:
        wq._mark_finished(j, killed=True)

    print wq.__dict__
    j = wq.pop(["render"])
    print j, jlist
    assert j is jlist[-1]
