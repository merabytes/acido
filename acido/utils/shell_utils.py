import os
import subprocess
import time
from huepy import bad, bold
from azure.core.exceptions import HttpResponseError

def wait_command(rg, cg, cont, wait=None, instance_manager=None):
    """
    Wait for a command to complete by polling container logs.
    
    Args:
        rg: Resource group name (kept for backward compatibility)
        cg: Container group name
        cont: Container name
        wait: Optional timeout in seconds
        instance_manager: InstanceManager instance for retrieving logs via Azure SDK
        
    Returns:
        tuple: (container_name, command_uuid, exception)
    """
    time_spent = 0
    exception = None
    command_uuid = None
    state_check_interval = 10  # Check container group state every 10 seconds
    last_state_check = 0
    
    # Get initial logs
    try:
        if instance_manager:
            container_logs = instance_manager.get_container_logs(cg, cont)
        else:
            # Fallback to CLI for backward compatibility (will fail in Lambda)
            container_logs = subprocess.check_output(
                f'az container logs --resource-group {rg} --name {cg} --container-name {cont}', 
                shell=True
            ).decode()
    except (subprocess.CalledProcessError, HttpResponseError) as e:
        exception = f"Failed to retrieve initial logs: {str(e)}"
        return cont, command_uuid, exception

    while True:
        # Check container group state periodically
        if instance_manager and (time_spent - last_state_check) >= state_check_interval:
            try:
                container_group = instance_manager.get(cg)
                if container_group:
                    # Check if provisioning failed
                    if container_group.provisioning_state == 'Failed':
                        exception = f"Container group '{cg}' is in Failed state"
                        break
                    
                    # Check individual container states if available
                    if hasattr(container_group, 'instance_view') and container_group.instance_view:
                        if hasattr(container_group.instance_view, 'state'):
                            if container_group.instance_view.state == 'Failed':
                                exception = f"Container group '{cg}' instance is in Failed state"
                                break
                        
                        # Check individual containers in the instance view
                        if hasattr(container_group.instance_view, 'events') and container_group.instance_view.events:
                            for event in container_group.instance_view.events:
                                if hasattr(event, 'type') and event.type == 'Error':
                                    exception = f"Container group '{cg}' has error event: {event.message if hasattr(event, 'message') else 'Unknown error'}"
                                    break
                        
                        if exception:
                            break
                
                last_state_check = time_spent
            except (HttpResponseError, AttributeError):
                # Don't fail the entire wait if state check fails, just continue
                # HttpResponseError: API call failures (e.g., network issues)
                # AttributeError: Missing attributes on container_group object
                pass
        
        try:
            if instance_manager:
                container_logs = instance_manager.get_container_logs(cg, cont)
            else:
                # Fallback to CLI for backward compatibility (will fail in Lambda)
                container_logs = subprocess.check_output(
                    f'az container logs --resource-group {rg} --name {cg} --container-name {cont}', 
                    shell=True
                ).decode()
        except (subprocess.CalledProcessError, HttpResponseError) as e:
            exception = f"Failed to retrieve logs: {str(e)}"
            break

        if wait and time_spent > wait:
            exception = 'TIMEOUT REACHED'
            break
        if 'command: ' in container_logs:
            parts = container_logs.split('command: ', 1)
            if len(parts) > 1:
                command_uuid = parts[1].strip()
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
        subprocess.Popen(["tmux", "send-keys", "-t", cont, f"acido -d {input_file}", "Enter"], env=env)
        time.sleep(5)
    subprocess.Popen(["tmux", "send-keys", "-t", cont, f"nohup acido -sh '{command}' > temp &", "Enter"], env=env)
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

