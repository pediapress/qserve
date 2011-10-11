#! /usr/bin/env py.test

import sys, time
from qs import proc


def test_run_cmd_with_this():
    st, out = proc.run_cmd([sys.executable, "-c" "import this"])
    assert "Namespaces are one honking great idea -- let's do more of those!" in out


def test_run_cmd_timeout():
    stime = time.time()
    st, out = proc.run_cmd([sys.executable, "-c" "import time; time.sleep(10)"], 0.5)
    needed = time.time() - stime
    assert (st, out) == (9, "")
    assert needed >= 0.49
    assert needed < 1.0


def test_run_cmd_trigger_loopexit():
    proc.run_cmd([sys.executable, "-uc", "import time, os, this; os.close(1); os.close(2); time.sleep(1)"])
