from reminders import start_scheduler
s = start_scheduler(None)
print('scheduler started:', bool(s))
if s:
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        print('scheduler type ok')
    except Exception as e:
        print('scheduler import error', e)
