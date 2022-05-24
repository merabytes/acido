# acido 0.12.1

Acido stands for **A**zure **C**ontainer **I**nstance **D**istributed **O**perations, with acido you can easily deploy container instances in Azure and distribute the workload of a particular task, for example, a port scanning task which has an input file with **x** hosts is splitted and distributed between **y** instances.

This tool is inspired by [axiom](https://github.com/pry0cc/axiom) where you can just spin up hundreds of instances to perform a distributed nmap/ffuf/screenshotting scan, and then delete them after they have finished. 

Depending on your quota limit you may need to open a ticket to Azure to request container group limits increase.

### Add an alias in .bashrc / .zshrc:
    alias acido='python3 -m acido.cli'
    
### Usage:
    usage: acido [-h] [-c] [-f FLEET] [-im IMAGE_NAME] [-n NUM_INSTANCES] [-t TASK] [-e EXEC_CMD] [-i INPUT_FILE] [-w WAIT] [-s SELECT] [-l] [-r REMOVE] [-in]
              [-sh SHELL] [-d DOWNLOAD_INPUT]

    optional arguments:
    -h, --help            show this help message and exit
    -c, --config          Start configuration of acido.
    -f FLEET, --fleet FLEET
                            Create new fleet.
    -im IMAGE_NAME, --image IMAGE_NAME
                            Deploy an specific image.
    -n NUM_INSTANCES, --num-instances NUM_INSTANCES
                            Instances that the operation affect
    -t TASK, --task TASK  Execute command as an entrypoint in the fleet.
    -e EXEC_CMD, --exec EXEC_CMD
                        Execute command on a running instance.
    -i INPUT_FILE, --input-file INPUT_FILE
                            The name of the file to use on the task.
    -w WAIT, --wait WAIT  Set max timeout for the instance to finish.
    -s SELECT, --select SELECT
                            Select instances matching name/regex.
    -l, --list              List all instances.
    -r REMOVE, --rm REMOVE
                            Remove instances matching name/regex.
    -in, --interactive    Start interactive acido session.
    -sh SHELL, --shell SHELL
                            Execute command and upload to blob.
    -d DOWNLOAD_INPUT, --download DOWNLOAD_INPUT
                            Download file contents remotely from the acido blob.

### Example usage with nmap
In this example we are going to:
* Create our base container image with acido (required) and nmap.
* Create 20 containers.
* Run a nmap scan using the 20 containers.

#### Step 1: Create the base image

Dockerfile (merabytes.azurecr.io/ubuntu:latest):

    FROM ubuntu:20.04

    RUN apt-get update && apt-get install python3 python3-pip python3-dev -y
    RUN python3 -m pip install acido
    RUN apt-get install nmap -y

    CMD ["sleep", "infinity"]

This will install acido & nmap on our base docker image (merabytes.azurecr.io/ubuntu:latest).

To upload the image to the registry, as always go to the folder of your Dockerfile and:

    docker login merabytes.azurecr.io
    docker build -t ubuntu .
    docker tag ubuntu merabytes.azurecr.io/ubuntu:latest
    docker push merabytes.azurecr.io/ubuntu:latest

#### Step 2: Run the scan


    $ acido -f ubuntu -n 20 --image merabytes.azurecr.io/ubuntu:latest -t 'nmap -iL input -p 0-200' -i file.txt

The result of doing this, is that acido automatically creates 2 container groups with 10 instances, splits the targets file into 20 chunks, uploads the chunks to the instances with the name "input", runs the (-t) command and after finishing, retrieves the output of the provided command of all the instances.

### Requirements

#### OS: Mac OS / Linux / Windows

#### Requirement 1: Login to Azure & Create an Azure Container Registry
    $ az login
    $ az acr create --resource-group Merabytes \
    --name merabytes --sku Basic

#### Requirement 2: Install acido and configure your RG & Registry
    pip install acido
    python3 -m acido.cli -c
    $ acido -c
    [+] Selecting I/O storage account (acido).
    [!] Please provide a Resource Group Name to deploy the ACIs: Merabytes
    [!] Image Registry Server: merabytes.azurecr.io
    [!] Image Registry Username: merabytes
    [!] Image Registry Password: *********
    $

#### Optional requirement (--exec): Install tmux & Patch Azure CLI
If you want to use --exec (similar to ssh) to execute commands on running containers having tmux installed and on PATH is mandatory. 

Also, for the --exec command to work properly, you need to monkey-patch a bug inside **az container exec** command in the sys.stdout.write function.

File: /lib/python3.9/site-packages/azure/cli/command_modules/container/custom.py

Line: 684

    def _cycle_exec_pipe(ws):
        r, _, _ = select.select([ws.sock, sys.stdin], [], [])
        if ws.sock in r:
            data = ws.recv()
            sys.stdout.write(data.decode() if isinstance(data, bytes) else data) # MODIFY THE LINE LIKE THIS
            sys.stdout.flush()
        if sys.stdin in r:
            x = sys.stdin.read(1)
            if not x:
                return True
            ws.send(x)
        return True

# Upcoming features

- [X] Add argument to specify docker image of the fleet
- [X] Add argument to execute scans through the Docker ENTRYPOINT (-t / --task)
- [ ] Test on Windows
- [ ] Add argument to retrieve ACI logs
- [ ] Add argument to create the fleet with a Network Group (route the traffic from all instances to a single Public IP)
- [ ] Get rid of monkey-patching of Azure CLI for --exec

# Credits / Acknowledgements

* Xavier Álvarez (xalvarez@merabytes.com)
* Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)
