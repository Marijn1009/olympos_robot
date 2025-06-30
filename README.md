# olympos_robot

Create a robot to sign up for Olympos sport lessons each week.

## Dev requirements

- Install [UV](https://github.com/astral-sh/uv)
- Run 'uv sync'
- Install 'pip install pre-commit'
- Run 'pre-commit install'
- Replace .env.template with .env file and correct secrets

## Running the robot

- Via terminal: ```uv run python -m robocorp.tasks run tasks.py -t main```
- Via sema4.ai extension: Go to @task in tasks.py and click 'run robot' or 'debug robot'

See output in work_directory/robot_attempts.jsonl and/or output directory.

## Unattended running

- Use Windows 'Task scheduler'
- In 'General' set "Run whether User is logged on or not"
- Define triggers
- Define action: Start a program ```"C:\WINDOWS\system32\cmd.exe"``` with argument ```/c "<<PATH_TO_ROBOT>>\run_robot_and_archive.cmd"```
- In 'Conditions' set "Wake the computer to run this task"
- In 'Settings' set:
  - "Stop the task if it runs longer than: 10 minutes"
  - "If the task is already running, then the following rule applies: Queue a new instance"
- Enable History
