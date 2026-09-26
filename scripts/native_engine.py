#!/usr/bin/env python3
"""Installation-time native fidelity check (not a live AtomSpace mutation)."""
import math
from pathlib import Path
import re
import sys
import sysconfig


def verify():
    from hyperon import MeTTa
    engine = MeTTa()
    for i in range(1500):
        engine.run('(cognitive-event "event-%s" "tool" "observed" "cap-%s" "hash-%s")' % (i, i, i))
    for i in range(96):
        engine.run('(cap-efficacy cap_%s (stv %s 0.8))' % (i, (i + 1) / 100))
    for i in range(96):
        result = str(engine.run('!(match &self (cap-efficacy cap_%s (stv $f $c)) (native-fidelity $f $c))' % i))
        values = re.findall(r'native-fidelity\s+([-\d.eE]+)\s+([-\d.eE]+)', result)
        if len(values) != 1 or not math.isclose(float(values[0][0]), (i + 1) / 100) or float(values[0][1]) != .8:
            raise RuntimeError('Native variable binding failed for cap_%s: %s' % (i, result))
    if engine.run('!(match &self (cap-efficacy absent $x) $x)') != [[]]:
        raise RuntimeError('Native engine invented an absent belief')
    print('Native fidelity verified: 96 exact bindings, 1500 event atoms, absent belief stays absent.')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--destination':
        print(Path(sysconfig.get_path('platlib')) / ('hyperonpy' + sysconfig.get_config_var('EXT_SUFFIX')))
    else:
        verify()
