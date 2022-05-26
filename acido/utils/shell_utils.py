import os
import subprocess
import time
from huepy import bad, bold

def wait_command(rg, cg, cont, wait=None):
    time_spent = 0
    exception = None
    command_uuid = None
    container_logs = subprocess.check_output(
        f'az container logs --resource-group {rg} --name {cg} --container-name {cont}', 
        shell=True
    )
    container_logs = container_logs.decode()

    while True:
        container_logs = subprocess.check_output(
        f'az container logs --resource-group {rg} --name {cg} --container-name {cont}', 
        shell=True
        )
        container_logs = container_logs.decode()

        if wait and time_spent > wait:
            exception = 'TIMEOUT REACHED'
            break
        if 'command: ' in container_logs:
            command_uuid = container_logs.split('command: ')[1].strip()
            break
        if 'Exception' in container_logs:
            exception = container_logs
            break
        time.sleep(1)
        time_spent += 1

    return cont, command_uuid, exception


def exec_command(rg, cg, cont, command, max_retries, input_file):
    env = os.environ.copy()
    env["PATH"] = "/usr/sbin:/sbin:" + env["PATH"]
    # Kill tmux window
    subprocess.Popen(["tmux", "kill-session", "-t", cont], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    subprocess.Popen(["tmux", "new-session", "-d", "-s", cont], env=env)
    time.sleep(5)
    subprocess.Popen(["tmux", "send-keys", "-t", cont,
                    f"az container exec -g {rg} -n {cg} --container-name {cont} --exec-command /bin/bash", "Enter",
                    ], env=env)
    time.sleep(15)
    if input_file:
        subprocess.Popen(["tmux", "send-keys", "-t", cont, f"python3 -m acido.cli -d {input_file}", "Enter"], env=env)
        time.sleep(5)
    subprocess.Popen(["tmux", "send-keys", "-t", cont, f"nohup python3 -m acido.cli -sh '{command}' > temp &", "Enter"], env=env)
    time.sleep(2)
    subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)

    output = subprocess.check_output(["tmux", "capture-pane", "-pt", cont], env=env).decode()

    time.sleep(4)

    retries = 0
    failed = False
    exception = None
    command_uuid = None

    while 'Done' not in output:

        retries += 1

        if retries > max_retries:
            exception = 'TIMEOUT REACHED'
            failed = True
            break

        subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)
        time.sleep(1)
        output = subprocess.check_output(["tmux", "capture-pane", "-pt", cont], env=env).decode()

        if 'Exit' in output:
            subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)
            time.sleep(2)
            subprocess.Popen(["tmux", "send-keys", "-t", cont, "cat temp", "Enter", "Enter"], env=env)
            time.sleep(2)
            subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)
            time.sleep(2)
            try:
                exception = subprocess.check_output(["tmux", "capture-pane", "-pt", cont], env=env)
                exception = exception.decode()
                exception = exception.split('cat temp')[1].strip()
            except Exception as e:
                exception = 'ERROR PARSING'
                print(bad(f'Error capturing output from: {bold(cont)}'))
            failed = True
            break
        if 'Done' in output:
            failed = False
            break

    if not failed:
        subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)
        time.sleep(2)
        subprocess.Popen(["tmux", "send-keys", "-t", cont, "cat temp", "Enter", "Enter"], env=env)
        time.sleep(10)
        subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)
        time.sleep(2)
        try:
            output = subprocess.check_output(["tmux", "capture-pane", "-pt", cont], env=env)
            output = output.decode()
            command_uuid = output.split('command: ')[1].split('\n')[0].strip()
        except Exception as e:
            command_uuid = None
            print(bad(f'Error capturing output from: {bold(cont)}'))
    else:
        print(bad(f'Exception ocurred while executing "{command}" from: {bold(cont)}'))

    # Kill shell
    subprocess.Popen(["tmux", "send-keys", "-t", cont, "(rm temp && exit)", "Enter"], env=env)
    time.sleep(1)
    # Kill tmux window
    subprocess.Popen(["tmux", "kill-session", "-t", cont], env=env)

    return cont, command_uuid, exception

