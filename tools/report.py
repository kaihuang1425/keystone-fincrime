"""Dev report: verdict and code per scenario group. Groups that split are where to look."""
import sys, os, collections, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'system'))
from triage.loader import Institution
from triage.decide import safe_decide
sys.stdout.reconfigure(encoding='utf-8')
root = sys.argv[1]
show = sys.argv[3] if len(sys.argv) > 3 else None
tot = collections.Counter()
for inst in sys.argv[2].split(','):
    I = Institution(os.path.join(root, inst))
    groups = collections.defaultdict(collections.Counter); ex = {}
    errs = 0
    for row in I.cases:
        r = safe_decide(I, row)
        t = r['_trace']
        if 'error' in t:
            errs += 1
            print('ERROR', r['case_id'], t['error'])
            continue
        g = ('+'.join(t['rules']), ','.join(d for d in t['docs'] if not (inst == 'payments_fx' and d == 'company_register_extract')) if True else '')
        key = (r['verdict'], r['reason_code'], 'open=' + '+'.join(t['open']), 'flags=' + '+'.join(c.replace('ESC_', '') for c in t['flags']))
        groups[g][key] += 1
        ex.setdefault((g, key), r)
        tot[(inst, r['verdict'])] += 1
    print('=====', inst, 'errors', errs)
    for g, cnt in sorted(groups.items()):
        mark = '  ' if len(cnt) == 1 else '!!'
        print('%s %s | %s | n=%d' % (mark, g[0], g[1], sum(cnt.values())))
        for key, n in cnt.most_common():
            r = ex[(g, key)]
            print('      %3d %-8s %-28s %s %s  ex=%s' % (n, key[0], key[1], key[2], key[3], r['case_id']))
            if show == 'reasons':
                print('          REASON: ' + r['reason'])
                print('          EVID:   ' + ', '.join(r['evidence']))
for k, v in sorted(tot.items()): print(k, v)
