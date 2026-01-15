# Scheduling start_electron_with_csharp.sh

This guide explains how to schedule the script to run automatically on Windows and Linux systems.

## Windows Setup

### Using Task Scheduler

1. **Open Task Scheduler**:
   - Press `Win + R`
   - Type `taskschd.msc`
   - Press Enter

2. **Create a new task**:
   - In the right panel, click "Create Basic Task"
   - Name: `Start Electron with C#`
   - Description: `Automatically starts Electron frontend and C# application`
   - Click "Next"

3. **Set the trigger**:
   - Select your preferred schedule:
     - **Daily**: Choose time (e.g., 9:00 AM)
     - **Weekly**: Choose day and time
     - **Monthly**: Choose date and time
   - Click "Next"

4. **Set the action**:
   - Action: `Start a program`
   - Program/script: `bash`
   - Add arguments: 
     ```
     C:\Users\Yonsuncrat\Videos\Algorithms and Data Structures\thoth\scripts\start_electron_with_csharp.sh
     ```
   - Start in: 
     ```
     C:\Users\Yonsuncrat\Videos\Algorithms and Data Structures\thoth
     ```
   - Click "Next"

5. **Finish**:
   - Review settings and click "Finish"
   - The task will now run automatically at the scheduled time

### Optional: Configure Advanced Settings

In Task Scheduler, right-click your task and select "Properties" to:
- Run with highest privileges (if needed)
- Run whether user is logged in or not
- Set it to run even if network is unavailable

---

## Linux Setup

### Using Cron

1. **Open crontab editor**:
   ```bash
   crontab -e
   ```

2. **Add a cron job**:
   
   At the end of the file, add a line using the following format:
   ```
   minute hour day month day-of-week /path/to/script.sh
   ```

   **Common examples**:
   
   - **Run daily at 9:00 AM**:
     ```bash
     0 9 * * * /home/user/thoth/scripts/start_electron_with_csharp.sh
     ```
   
   - **Run every 2 hours**:
     ```bash
     0 */2 * * * /home/user/thoth/scripts/start_electron_with_csharp.sh
     ```
   
   - **Run every Monday at 2:30 PM**:
     ```bash
     30 14 * * 1 /home/user/thoth/scripts/start_electron_with_csharp.sh
     ```
   
   - **Run every 15 minutes**:
     ```bash
     */15 * * * * /home/user/thoth/scripts/start_electron_with_csharp.sh
     ```

3. **Save and exit**:
   - Press `Ctrl + X`, then `Y`, then `Enter` (if using nano)
   - Or follow your editor's save instructions

4. **Verify the cron job**:
   ```bash
   crontab -l
   ```

### Cron Time Format Reference

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * * /path/to/script.sh
```

**Special characters**:
- `*` = any value
- `,` = specific values (e.g., `1,3,5` = 1st, 3rd, 5th)
- `-` = range (e.g., `1-5` = 1 through 5)
- `/` = step values (e.g., `*/5` = every 5 units)

### Redirecting Output (Optional)

To log the script output, append to your cron job:
```bash
0 9 * * * /home/user/thoth/scripts/start_electron_with_csharp.sh >> /home/user/thoth/logs/cron.log 2>&1
```

Create the logs directory if it doesn't exist:
```bash
mkdir -p /home/user/thoth/logs
```

---

## Cross-Platform Python Scheduler (Alternative)

If you prefer a unified approach, create a Python scheduler:

1. **Install APScheduler**:
   ```bash
   pip install apscheduler
   ```

2. **Create `scripts/scheduler.py`**:
   ```python
   from apscheduler.schedulers.background import BackgroundScheduler
   import subprocess
   import os
   import sys

   def run_script():
       script_path = os.path.join(os.path.dirname(__file__), 'start_electron_with_csharp.sh')
       try:
           subprocess.run(['bash', script_path], check=True)
           print(f"[{os.uname()[1]}] Script executed successfully")
       except Exception as e:
           print(f"[ERROR] Failed to execute script: {e}")

   # Configure scheduler
   scheduler = BackgroundScheduler()
   scheduler.add_job(run_script, 'cron', hour=9, minute=0)
   scheduler.start()

   print("Scheduler running. Press Ctrl+C to exit.")
   try:
       while True:
           pass
   except KeyboardInterrupt:
       print("Shutting down scheduler...")
       scheduler.shutdown()
   ```

3. **Run the scheduler**:
   ```bash
   python scripts/scheduler.py
   ```

This approach works identically on Windows and Linux.
