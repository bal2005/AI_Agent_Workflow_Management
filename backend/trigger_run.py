from app.scheduler_tasks import run_schedule
result = run_schedule.apply(args=[7, 'manual'])
print("Result:", result.result)
