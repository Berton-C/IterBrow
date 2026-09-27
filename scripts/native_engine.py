#!/usr/bin/env python3
"""Installation-time native fidelity check (not a live AtomSpace mutation)."""
import hashlib
import importlib.util
import math
from pathlib import Path
import re
import sys
import sysconfig


# hyperon==0.2.10 CPython 3.12 macOS extension hashes.  Both published
# binaries contain the TrieKey::value precedence defect fixed by IterBrow's
# pinned source patch.  Detect them without importing or exercising the
# extension: the distinguishing runtime operation aborts Python rather than
# raising an exception, which would produce a macOS crash report during an
# otherwise normal installation.
KNOWN_BROKEN_MACOS_BINARIES = {
    "19afc1394dcbd15e36bea835ea7ae1cf9fe76f25cc1f8aa1a99ccbd411d4a3c0",  # arm64
    "60a42263f1607c23685febe226d46cf12d8962d101ba0f181e582e31dde31c4b",  # x86_64
}


def safe_preflight():
    spec = importlib.util.find_spec("hyperonpy")
    if spec is None or not spec.origin:
        raise RuntimeError("hyperonpy native extension is not installed")
    native_path = Path(spec.origin)
    digest = hashlib.sha256(native_path.read_bytes()).hexdigest()
    if digest in KNOWN_BROKEN_MACOS_BINARIES:
        raise RuntimeError(
            "published Hyperon 0.2.10 macOS binary has the AtomSpace "
            "enumeration defect; IterBrow native repair is required"
        )
    print("Native preflight accepted %s (%s...)" % (native_path.name, digest[:12]))


def verify():
    from hyperon import MeTTa
    engine = MeTTa()
    for i in range(2500):
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
    # Hyperon 0.2.10's published macOS wheel contains an operator-precedence
    # defect in TrieKey::value().  Small queries still pass, but enumerating a
    # realistically sized AtomSpace aborts the entire Python process in
    # space_iterate.  This is the distinguishing check for IterBrow's pinned
    # native repair; ordinary import/query smoke tests cannot detect the bug.
    atoms = engine.space().get_atoms()
    expected_atoms = 2500 + 96
    if len(atoms) != expected_atoms:
        raise RuntimeError(
            'Native AtomSpace enumeration returned %s atoms; expected %s'
            % (len(atoms), expected_atoms)
        )
    print(
        'Native fidelity verified: 96 exact bindings, 2500 event atoms, '
        'complete enumeration, absent belief stays absent.'
    )


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--destination':
        print(Path(sysconfig.get_path('platlib')) / ('hyperonpy' + sysconfig.get_config_var('EXT_SUFFIX')))
    elif len(sys.argv) > 1 and sys.argv[1] == '--safe-preflight':
        safe_preflight()
    else:
        verify()
