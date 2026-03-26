from database import get_all_dc_entries, get_dc_entry

es = get_all_dc_entries(10)
print('entries_count=', len(es))
for i,e in enumerate(es):
    print('\n--- entry', i)
    try:
        print('keys=', list(e.keys()))
    except Exception:
        print('entry repr=', repr(e))
    eid = e.get('id')
    print('id raw =', repr(eid), 'type=', type(eid))
    print('dc_no =', repr(e.get('dc_no')))
    try:
        r1 = get_dc_entry(eid)
        print('get_dc_entry by id ->', 'FOUND' if r1 else 'NOT FOUND')
    except Exception as ex:
        print('get_dc_entry by id -> ERROR', ex)
    try:
        r2 = get_dc_entry(e.get('dc_no'))
        print('get_dc_entry by dc_no ->', 'FOUND' if r2 else 'NOT FOUND')
    except Exception as ex:
        print('get_dc_entry by dc_no -> ERROR', ex)
    if 'r1' in locals() and r1:
        print('header id type:', type(r1.get('header').get('id')),
              'header id repr:', r1.get('header').get('id'))
