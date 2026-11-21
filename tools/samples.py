"""Print one reason per (rules, docs, code) group for reading."""
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'system'))
from triage.loader import Institution
from triage.decide import safe_decide
sys.stdout.reconfigure(encoding='utf-8')
root, insts = sys.argv[1], sys.argv[2].split(',')
skip = int(sys.argv[3]) if len(sys.argv) > 3 else 0
for inst in insts:
    I = Institution(os.path.join(root, inst))
    seen = collections.Counter()
    print('=====', inst)
    for row in I.cases:
        r = safe_decide(I, row)
        t = r['_trace']
        key = ('+'.join(t.get('rules', [])), ','.join(d for d in t.get('docs', []) if d != 'company_register_extract' or inst != 'payments_fx'), r['reason_code'])
        seen[key] += 1
        if seen[key] != skip + 1:
            continue
        n = len([s for s in r['reason'].replace('Ltd.', 'Ltd').split('. ') if s.strip()])
        print('[%s | %s] %s %s  (%s, ~%d sentences, %d chars)' % (key[0], key[1], r['verdict'], r['reason_code'], r['case_id'], n, len(r['reason'])))
        print('   ' + r['reason'])
        print('   evidence: ' + ', '.join(r['evidence']))
