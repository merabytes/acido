# acido 0.10.14

Acido stands for **A**zure **C**ontainer **I**nstance **D**istributed **O**perations, with acido you can easily deploy container instances in Azure and distribute the workload of a particular task, for example, a port scanning task which has an input file with **x** hosts is splitted and distributed between **y** instances.

This tool is inspired by [axiom](https://github.com/pry0cc/axiom) where you can just spin up hundreds of instances to perform a distributed nmap/ffuf/screenshotting scan, and then delete them after they have finished. 

Depending on your quota limit you may need to open a ticket to Azure to request container group limits increase.

### Add an alias in .bashrc / .zshrc:
    alias acido='python3 -m acido.cli'
    
### Usage:
    usage: acido [-h] [-f FLEET] [-n NUM_INSTANCES] [-l] [-e EXEC_CMD] [-s SELECT] [-r REMOVE] [-c]
                [-w WAIT] [-i INPUT_FILE] [-in] [-sh SHELL] [-d DOWNLOAD_INPUT]

    optional arguments:
    -h, --help            show this help message and exit
    -f FLEET, --fleet FLEET
                            Create new fleet.
    -n NUM_INSTANCES, --num-instances NUM_INSTANCES
                            Instances that the operation affect
    -l, --list            List all instances.
    -e EXEC_CMD, --exec EXEC_CMD
                            Execute command in all selected instances.
    -s SELECT, --select SELECT
                            Select instances matching name/regex.
    -r REMOVE, --rm REMOVE
                            Remove instances matching name/regex.
    -c, --config          Start configuration of acido.
    -w WAIT, --wait WAIT  Number of seconds to wait for the command to finish.
    -i INPUT_FILE, --input-file INPUT_FILE
                            The name of the file to split.
    -in, --interactive    Start interactive acido session.
    -sh SHELL, --shell SHELL
                            Execute command and upload to blob.
    -d DOWNLOAD_INPUT, --download DOWNLOAD_INPUT
                            Download file contents remotely from the acido blob.

### Example usage with nmap
In this example we are going to use acido to:
* Create 3 containers
* Install nmap on the containers
* Use the created containers to gather the output of an nmap scan against a list containing 6 targets.

The result of doing this, is that acido automatically splits the target file into 3 files to scan the hosts in parallel and retrieves the output of the 3 containers.

NOTE: For scans that can take longer than 1 minute, you must specify -w TIMEOUT where timeout is the number of seconds we should wait for output.


     $ acido -f ubuntu -n 3
     [+] Selecting I/O storage account (acido).
     [+] Successfully created new group/s: [ ubuntu ]
     [+] Successfully created new instance/s: [ ubuntu-01 ubuntu-02 ubuntu-03 ]
     
     $ sleep 300
     # Wait 300 seconds for the instances to install acido
     
     $ acido -s 'ubuntu'
     [+] Selecting I/O storage account (acido).
     [+] Selected all instances of group/s: [ ubuntu ]
     
     $ acido -e 'apt-get install nmap -y'
     [+] Selecting I/O storage account (acido).
     [+] Executed command on ubuntu-01. Output: [
      Reading package lists...
      ...
      ]
     [+] Executed command on ubuntu-02. Output: [
      Reading package lists...
      ...
      ]
     [+] Executed command on ubuntu-03. Output: [
      Reading package lists...
      ...
      ]
      
     $ cat file.txt
     xavi.al
     merabytes.com
     intimepharma.eu
     intimetransport.eu
     bandit.cat
     bandit.solutions
     
     $ acido -e 'nmap -iL input -p 0-200' -i file.txt
    [+] Selecting I/O storage account (acido).
    [+] Splitting into 3 files.
    [+] Uploaded input: 1b497def-2a1d-4e47-a6b6-99087c052cfc
    [+] Uploaded input: 24d9e72e-8fe9-46e4-b778-d86b16847cdf
    [+] Uploaded input: f844ae29-09bb-4849-881e-ba03eef33552
    
    [+] Executed command on ubuntu-01. Output: [
    Starting Nmap 7.80 ( https://nmap.org ) at 2022-05-23 22:31 UTC
    Nmap scan report for xavi.al (159.69.206.65)
    ...
    
    Nmap scan report for merabytes.com (159.69.206.65)
    ...
    
    Nmap done: 2 IP addresses (2 hosts up) scanned in 0.54 seconds
    ]
    
    [+] Executed command on ubuntu-02. Output: [
    Starting Nmap 7.80 ( https://nmap.org ) at 2022-05-23 22:31 UTC
    Nmap scan report for intimepharma.eu (217.160.0.36)
    ...
    
    Nmap scan report for intimetransport.eu (217.160.0.36)
    ...
    
    Nmap done: 2 IP addresses (2 hosts up) scanned in 4.03 seconds
    ]
    [+] Executed command on ubuntu-03. Output: [
    Starting Nmap 7.80 ( https://nmap.org ) at 2022-05-23 22:31 UTC
    Nmap scan report for bandit.cat (35.214.153.47)
    Host is up (0.014s latency).
    ...
    
    Nmap scan report for bandit.solutions (35.214.153.47)
    Host is up (0.013s latency).
    ...
    
    Nmap done: 2 IP addresses (2 hosts up) scanned in 5.04 seconds
    ]


### Requirements

#### OS: Mac OS / Linux

#### Requirement 1: Install tmux
Because the commands are executed through multiplexing tmux is mandatory. The tool has only been tested on Mac OS, but should work on Linux.

#### Requirement 2: Login to Azure & Create an Azure Container Registry
    $ az login
    $ az acr create --resource-group Merabytes \
    --name merabytes --sku Basic

#### Requirement 3: Install acido and configure your RG & Registry
    pip install acido
    python3 -m acido.cli -c
    $ acido -c
    [+] Selecting I/O storage account (acido).
    [!] Please provide a Resource Group Name to deploy the ACIs: Merabytes
    [!] Image Registry Server: merabytes.azurecr.io
    [!] Image Registry Username: merabytes
    [!] Image Registry Password: *********
    $

#### Requirement 4: Monkey Patching Azure CLI to use az container exec
In order for the tool to work properly, you need to monkey-patch a bug inside **az container exec** command in the sys.stdout.write function.

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

- [ ] Add argument to specify docker image of the fleet
- [ ] Add argument to execute scans through the Docker ENTRYPOINT
- [ ] Add argument to retrieve ACI logs
- [ ] Add argument to create the fleet with a Network Group (route the traffic from all instances to a single Public IP)
- [ ] Get rid of monkey-patching of Azure CLI

# Credits / Acknowledgements

* Xavier Álvarez (xalvarez@merabytes.com)
* Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)
