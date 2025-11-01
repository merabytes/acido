# acido (0.17)

Acido stands for **A**zure **C**ontainer **I**nstance **D**istributed **O**perations, with acido you can easily deploy container instances in Azure and distribute the workload of a particular task, for example, a port scanning task which has an input file with **x** hosts is splitted and distributed between **y** instances.

This tool is inspired by [axiom](https://github.com/pry0cc/axiom) where you can just spin up hundreds of instances to perform a distributed nmap/nuclei/screenshotting scan, and then delete them after they have finished. 

Depending on your quota limit you may need to open a ticket to Azure to request container group limits increase.

A little diagram on how the acido CLI works, for example with Nuclei:

![acido](https://user-images.githubusercontent.com/15344287/170670823-1e3b0de3-2834-4d38-a21d-368c50f073d3.png)

### Add an alias in .bashrc / .zshrc:
    alias acido='python3 -m acido.cli'
    
### Usage:
    usage: acido [-h] [-c] [-f FLEET] [-im IMAGE_NAME] [--create-ip CREATE_IP] [--ip] [-n NUM_INSTANCES] [-t TASK] [-e EXEC_CMD] [-i INPUT_FILE] [-w WAIT] [-s SELECT] [-l] [-r REMOVE] [-in]
              [-sh SHELL] [-d DOWNLOAD_INPUT] [-o WRITE_TO_FILE] [-rwd]

    optional arguments:
    -h, --help            show this help message and exit
    -c, --config          Start configuration of acido.
    -f FLEET, --fleet FLEET
                            Create new fleet.
    -im IMAGE_NAME, --image IMAGE_NAME
                            Deploy an specific image.
    --create-ip CREATE_IP Create a new IPv4 address and network profile for routing container traffic.
    --ip                  Select an existing IPv4 address to route containers through.
    -n NUM_INSTANCES, --num-instances NUM_INSTANCES
                            Instances that the operation affect
    -t TASK, --task TASK  Execute command as an entrypoint in the fleet.
    -e EXEC_CMD, --exec EXEC_CMD
                        Execute command on the selected instances.
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
    -o WRITE_TO_FILE, --output WRITE_TO_FILE
                        Save the output of the machines in JSON format.
    -rwd, --rm-when-done  Remove the container groups after finish.


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


    $ cat file.txt
    merabytes.com
    uber.com
    facebook.com
    ...

    $ acido -f ubuntu \
            -n 20 \
            --image merabytes.azurecr.io/ubuntu:latest \
            -t 'nmap -iL input -p 0-200' \
            -i file.txt \
            -o output

    [+] Selecting I/O storage account (acido).
    [+] Splitting into 20 files.
    [+] Uploaded 20 targets lists.
    [+] Successfully created new group/s: [ ubuntu-01 ubuntu-02 ]
    [+] Successfully created new instance/s: [ ubuntu-01-01 ubuntu-01-02 ubuntu-01-03 ubuntu-01-04 ubuntu-01-05 ubuntu-01-06 ubuntu-01-07 ubuntu-01-08 ubuntu-01-09 ubuntu-01-10 ubuntu-02-01 ubuntu-02-02 ubuntu-02-03 ubuntu-02-04 ubuntu-02-05 ubuntu-02-06 ubuntu-02-07 ubuntu-02-08 ubuntu-02-09 ubuntu-02-10 ]
    [+] Waiting 2 minutes until the machines get provisioned...
    [+] Waiting for outputs...
    [+] Executed command on ubuntu-02-01. Output: [
    Starting Nmap 7.80 ( https://nmap.org ) at ...
    ...
    ]
    [+] Executed command on ubuntu-02-02. Output: [
    Starting Nmap 7.80 ( https://nmap.org ) at ...
    ...
    ]
    ...
    [+] Saved container outputs at: output.json
    [+] Saved merged outputs at: all_output.txt.


The result of doing this, is that acido automatically creates 2 container groups with 10 instances, splits the targets file into 20 chunks, uploads the chunks to the instances with the name "input", runs the command provided with -t and after finishing, saves the output to a JSON file.

### Requirements

#### OS: Mac OS / Linux / Windows

#### Requirement 1: Login to Azure & Create an Azure Container Registry
    $ az login
    $ az acr create --resource-group Merabytes \
    --name merabytes --sku Basic

> **Note:** For production use or CI/CD pipelines, consider creating a Service Principal with appropriate permissions. See [.github/AZURE_PERMISSIONS.md](.github/AZURE_PERMISSIONS.md) for detailed instructions on setting up Azure permissions and authentication.

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

### Troubleshooting

#### Setting Flags for OpenSSL on Devices using Apple Silicon

If you are on an Apple Silicon device, follow these steps to install `openssl@1.1` and set the necessary environment variables:

1. **Install OpenSSL@1.1**:
    Use Homebrew to install `openssl@1.1`.
    ```bash
    brew install openssl@1.1
    ```

2. **Set Environment Variables**:
    Export the necessary environment variables to point to the correct library and include directories.
    ```bash
    export LDFLAGS="-L/opt/homebrew/opt/openssl@1.1/lib"
    export CPPFLAGS="-I/opt/homebrew/opt/openssl@1.1/include"
    ```

3. **Verify Your Configuration**:
    You can verify the installation and see the suggested environment variables by checking the information provided by Homebrew.
    ```bash
    brew info openssl
    ```

By following these steps, you should have `openssl@1.1` installed and the necessary flags set for your Apple Silicon device.


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

# Architecture

## Internal Architecture Overview

Acido is designed with a modular architecture that makes it easy to support multiple security tools and efficiently distribute workloads across Azure Container Instances. The system consists of several key components that work together seamlessly:

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Acido CLI                                │
│                      (User Interface)                            │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ├──────────────────────────────────────────────┐
                  │                                              │
                  ▼                                              ▼
    ┌─────────────────────────┐              ┌──────────────────────────┐
    │   InstanceManager       │              │     BlobManager          │
    │  - Deploy containers    │              │  - Upload/download files │
    │  - Manage lifecycle     │◄────────────►│  - Store outputs         │
    │  - Execute commands     │              │  - Input distribution    │
    └────────┬────────────────┘              └──────────┬───────────────┘
             │                                          │
             │ Uses Managed Identity                    │
             ▼                                          ▼
    ┌─────────────────────────┐              ┌──────────────────────────┐
    │  Azure Container        │              │  Azure Blob Storage      │
    │  Instances (ACIs)       │              │  - Container: acido      │
    │  - Run security tools   │◄────────────►│  - Inputs & Outputs      │
    │  - Process data chunks  │   Download   │  - UUIDs for tracking    │
    └─────────────────────────┘   via MI     └──────────────────────────┘
```

### How It Works

#### 1. Input File Distribution via Blob Storage

When you run a distributed scan with an input file, acido follows this workflow:

```
Host Machine                     Blob Storage                Container Instances
┌─────────────┐                 ┌─────────────┐            ┌──────────────────┐
│ input.txt   │                 │             │            │  Container 1     │
│ (1000 lines)│                 │             │            │  ┌────────────┐  │
└──────┬──────┘                 │             │            │  │ input (50) │  │
       │                        │             │            │  └────────────┘  │
       │ 1. Split into chunks   │             │            └──────────────────┘
       ├────────────────────────┤             │
       │   Chunk 1 (50 lines)   │──Upload────►│ UUID-1     │  ┌──────────────────┐
       │   Chunk 2 (50 lines)   │──Upload────►│ UUID-2     │  │  Container 2     │
       │   Chunk 3 (50 lines)   │──Upload────►│ UUID-3     │  │  ┌────────────┐  │
       │   ...                  │             │            │  │  │ input (50) │  │
       │   Chunk 20 (50 lines)  │──Upload────►│ UUID-20    │  │  └────────────┘  │
       └────────────────────────┘             │            │  └──────────────────┘
                                              │            │           ...
                                              │            │  ┌──────────────────┐
                                              │            │  │  Container 20    │
                                              └────Download──►│  ┌────────────┐  │
                                                   via MI  │  │  │ input (50) │  │
                                                           │  │  └────────────┘  │
                                                           │  └──────────────────┘
```

**Steps:**
1. **File Splitting**: The CLI splits the input file into N chunks (where N = number of instances)
2. **Blob Upload**: Each chunk is uploaded to blob storage with a unique UUID identifier
3. **Container Deployment**: Containers are deployed with environment variables containing:
   - Blob storage account name
   - Managed Identity client ID
   - UUID of their assigned input chunk
4. **Download in Container**: Each container uses Managed Identity to authenticate and download its input chunk
5. **Processing**: The security tool processes its chunk independently
6. **Output Collection**: Results are uploaded back to blob storage and collected by the CLI

#### 2. Managed Identity for Secure Access

Acido uses **Azure Managed Identity** to provide containers with secure, credential-free access to blob storage:

```
┌────────────────────────────────────────────────────────────────┐
│  Container Instance (ACI)                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Environment Variables:                                   │  │
│  │  - IDENTITY_CLIENT_ID: <managed-identity-client-id>      │  │
│  │  - STORAGE_ACCOUNT_NAME: <storage-account>               │  │
│  │  - RG: <resource-group>                                  │  │
│  └────────────────────────┬─────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ManagedAuthentication Class                             │  │
│  │  - Detects cloud environment (MSI_ENDPOINT)              │  │
│  │  - Uses ManagedIdentityCredential with client_id         │  │
│  │  - Obtains access token for storage.azure.com            │  │
│  └────────────────────────┬─────────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────────┘
                            │ Token-based authentication
                            ▼
               ┌─────────────────────────────┐
               │  Azure Blob Storage         │
               │  - Validates MI token       │
               │  - Grants read/write access │
               └─────────────────────────────┘
```

**Benefits:**
- **No credentials in code or environment**: No storage account keys needed in containers
- **Automatic token management**: Azure handles token lifecycle
- **Fine-grained permissions**: RBAC controls what each identity can access
- **Audit trail**: All access logged in Azure Activity Logs

#### 3. Supporting Multiple Security Tools

The architecture is designed to be **tool-agnostic**, making it easy to support any security tool:

```
┌─────────────────────────────────────────────────────────────────┐
│  Acido Abstraction Layer                                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Generic Command Execution Framework                       │ │
│  │  - Input file handling (--input-file)                      │ │
│  │  - Command wrapper (--task)                                │ │
│  │  - Output collection (--output)                            │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┬────────────────┐
          │               │               │                │
          ▼               ▼               ▼                ▼
    ┌─────────┐     ┌─────────┐    ┌──────────┐    ┌──────────┐
    │  nmap   │     │ nuclei  │    │ masscan  │    │ nikto    │
    │         │     │         │    │          │    │          │
    │ -iL     │     │ -list   │    │ -iL      │    │ -h       │
    │ input   │     │ input   │    │ input    │    │ input    │
    └─────────┘     └─────────┘    └──────────┘    └──────────┘
```

**Key Design Principles:**

1. **Standard Input/Output Pattern**: All tools read from a file named `input` and write to stdout
2. **Docker Entrypoint Execution**: Commands run via `-t` flag use the container's entrypoint
3. **Environment Variable Injection**: Tools can access blob storage, registry credentials, etc.
4. **Result Aggregation**: Outputs are collected via blob storage and merged by CLI

**Example with different tools:**

```bash
# Nmap scan
acido -f nmap-fleet -n 20 -im registry.io/nmap:latest \
  -t 'nmap -iL input -p 1-1000' -i targets.txt

# Nuclei scan
acido -f nuclei-fleet -n 50 -im registry.io/nuclei:latest \
  -t 'nuclei -list input -t /nuclei-templates/' -i urls.txt

# Masscan scan
acido -f masscan-fleet -n 30 -im registry.io/masscan:latest \
  -t 'masscan -iL input -p0-65535' -i targets.txt
```

### Data Flow Summary

```
1. User invokes CLI with task and input file
                    ↓
2. CLI authenticates to Azure (az login or environment credentials)
                    ↓
3. Input file split into N chunks (N = number of instances)
                    ↓
4. Chunks uploaded to blob storage (acido container)
                    ↓
5. Container groups created with:
   - Base image with security tool + acido installed
   - Managed Identity attached
   - Environment variables (IDENTITY_CLIENT_ID, STORAGE_ACCOUNT_NAME, etc.)
   - Command: download input chunk → run security tool → upload output
                    ↓
6. Containers start and use Managed Identity to:
   - Download their assigned input chunk from blob
   - Execute the security tool command
   - Upload results back to blob storage
                    ↓
7. CLI polls containers for completion
                    ↓
8. CLI downloads outputs from blob storage
                    ↓
9. Results aggregated and saved (JSON + merged text file)
                    ↓
10. Optional: Containers deleted (--rm-when-done)
```

### Component Details

#### InstanceManager
- **Purpose**: Manages Azure Container Instance lifecycle
- **Key Methods**:
  - `deploy()`: Creates container groups with specified configuration
  - `provision()`: Configures individual container instances
  - `rm()`: Deletes container groups
  - `ls()`: Lists all running instances
- **Features**:
  - Automatic splitting of >10 instances into multiple container groups (Azure limit)
  - Managed Identity attachment for blob access
  - Image registry authentication
  - Network profile support for custom IP routing

#### BlobManager
- **Purpose**: Handles all blob storage operations
- **Key Methods**:
  - `upload()`: Uploads data with UUID naming
  - `download()`: Retrieves files by UUID
  - `use_container()`: Selects/creates storage container
- **Authentication**: Supports managed identity, environment credentials, and connection strings
- **Features**: Automatic UUID generation for file tracking

#### ManagedAuthentication
- **Purpose**: Provides unified authentication across Azure services
- **Credential Chain**:
  1. Cloud: Managed Identity → Environment Credentials
  2. Local: Azure CLI → Environment Credentials → Client Secret
- **Auto-detection**: Automatically detects cloud vs. local environment

#### NetworkManager
- **Purpose**: Manages virtual networks and public IPs for container groups
- **Key Methods**:
  - `create_ipv4()`: Creates public IP addresses
  - `create_virtual_network()`: Sets up VNets
  - `create_network_profile()`: Creates network profiles for ACIs
- **Use Case**: Route all container traffic through a single public IP

### Traffic Routing for Security Audits

Acido supports routing all container traffic through a single public IPv4 address, which is particularly valuable for security audits and penetration testing engagements:

#### How It Works

```
┌────────────────────────────────────────────────────────────────┐
│  Single Public IP (e.g., 20.123.45.67)                         │
│  Created with: acido --create-ip my-pentest-ip                 │
└────────────────┬───────────────────────────────────────────────┘
                 │ All outbound traffic routes through this IP
                 │
    ┌────────────┼────────────┬────────────┬────────────┐
    │            │            │            │            │
    ▼            ▼            ▼            ▼            ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│Container│ │Container│ │Container│ │Container│ │Container│
│   1     │ │   2     │ │   3     │ │  ...    │ │   50    │
└─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
    │            │            │            │            │
    └────────────┴────────────┴────────────┴────────────┘
                             │
                   Distributed scanning
                             ▼
                    ┌─────────────────┐
                    │  Target Network │
                    │  (Client site)  │
                    └─────────────────┘
```

#### Benefits for Penetration Testing

1. **Simplified IP Whitelisting**: 
   - Instead of whitelisting dozens or hundreds of container IPs, security teams only need to whitelist a single IP address
   - Reduces firewall rule complexity and management overhead
   - Makes it easier to coordinate with client security teams

2. **Larger Scale Testing**:
   - Deploy 50, 100, or more containers for distributed scanning
   - All traffic appears to originate from the whitelisted IP
   - Achieve significantly higher throughput than traditional single-machine scans
   - Complete comprehensive scans in a fraction of the time

3. **Audit Trail and Compliance**:
   - All scan traffic is associated with a single, documented IP address
   - Easier to track and correlate security testing activities
   - Simplifies incident response if alerts are triggered
   - Meets compliance requirements for authorized testing

4. **Professional Engagement Workflow**:
   - Create IP before engagement: `acido --create-ip client-pentest-2024`
   - Provide IP to client for whitelisting
   - Deploy fleet with IP routing: `acido -f scan-fleet -n 50 --ip -t '...'`
   - All containers automatically use the whitelisted IP
   - Clean up after engagement

**Example Usage:**

```bash
# Create a new public IP for the pentest engagement
acido --create-ip acme-corp-pentest

# Provide the IP address (shown in output) to client for whitelisting
# Example: 20.123.45.67

# Once whitelisted, deploy your fleet routing through this IP
acido -f nmap-fleet -n 50 --ip \
  -im registry.io/nmap:latest \
  -t 'nmap -iL input -p- -T4' \
  -i targets.txt

# All 50 containers will scan through the single whitelisted IP
# Achieving 50x parallelization while maintaining a single source IP
```

This approach combines the **scale and speed** of distributed scanning with the **simplicity and control** required for professional security engagements.

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
