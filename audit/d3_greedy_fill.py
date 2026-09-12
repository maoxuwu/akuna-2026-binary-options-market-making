"""Scenario (a): GREEDY FILL sessions across cash {10,20,40}, 20-45 days,
platform-like option flow, every quote filled full-qty on the chosen side,
every accepted FOK filled. External grader ledger asserted >= 0 at each day end."""
import sys
sys.path.insert(0, '<WORKDIR>/audit')
from d3_common import run_session, show

worst = None
for cash in (10, 20, 40):
    for seed in (1, 2, 3, 4):
        for mode in ('drain', 'adverse'):
            n_days = {1: 20, 2: 30, 3: 45, 4: 25}[seed]
            r = run_session(cash, seed, n_days, mode)
            show(r)
            key = r['min_dayend']
            if worst is None or key < worst[0]:
                worst = (key, r['cash'], r['seed'], r['mode'])

# one capped-fill (qty<=30, platform-realistic client size) pass for comparison
print('--- capped fills (<=30 lots) ---')
for cash in (10, 40):
    for mode in ('drain', 'adverse'):
        r = run_session(cash, 5, 30, mode, fill_cap=30)
        show(r)
        if r['min_dayend'] < worst[0]:
            worst = (r['min_dayend'], r['cash'], r['seed'], r['mode'])

print('WORST min day-end external ledger:', worst)
