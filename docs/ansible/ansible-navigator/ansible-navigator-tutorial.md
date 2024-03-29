
# A BLAZINGLY-FAST ANSIBLE NAVIGATOR TUTORIAL

Below might be the quickest Ansible Navigator tutorial going (for the tutorial itself, you should feel totally free to jump right to the “[Steps](#steps)“), that with even a tiny bit of practice should make you blazingly-fast in developing and testing your Ansible playbooks and roles on the command line, even when compared to the Ansible community’s traditional (and fairly quick in their own right) methods.

(For those who may be interested in learning more about _why_ Ansible Navigator was created and exactly _how_ it builds upon many of the great features of established tools like `ansible-playbook` and the rest of the _ansible-*_ toolbox, you can check out the longer “Background” which immediately follows. 

## Background

Ansible Navigator (`ansible-navigator`) is a seriously powerful text user interface (TUI) tool that offers new and even better ways to interact with your Ansible environment and content, a tool which both owes a debt to the lasting legacies of `ansible-playbook` and its related programs, while also delivering much-needed new features (and feature consolidations) that have been leaving the traditional Ansible CLI toolbox a bit lacking in recent times– especially as the Red Hat Ansible Automation Platform (AAP) codebase and ecosystem continue to evolve and improve rapidly for AAP customers.

While your initial impressions might make it seem a bit more complex than good ol’ ansible-playbook, the reality is that Ansible Navigator is actually designed to simplify and accelerate your early-and-often Ansible CLI efforts by providing a more visual experience for Ansible playbook and role developers going forward. Ansible Navigator allows you to explore and manage your Ansible content in a much more intuitive manner. The tutorial later in this post will guide you through the essential concepts and usage of Ansible Navigator, so that you can start using it in your Ansible automation development and testing workflows right away.

Both Ansible Navigator and ansible-playbook are fundamentally CLI tools that you can use to interact with Ansible, but they differ a fair amount in their approach and features.

1.  Main usage comparison:
    -   ansible-playbook is used primarily for executing Ansible playbooks.
    -   Ansible Navigator is considered a more comprehensive tool designed to explore, manage, and execute Ansible content, including playbooks, roles, and collections, while also allowing you to use the exact same execution environment (EE) images you do in AAP. More on this highlight in a minute but Ansible Navigator is a complete game-changer for AAP customers, because it bridges a major CLI gap that would have otherwise existed between Ansible Tower’s Python virtualenv approach of yesteryear and AAP’s modern EE approach of today and the future.
2.  UI comparison:
    -   ansible-playbook has a traditional CLI interface, where you run playbooks by passing flags and specifying playbook files.
    -   Ansible Navigator features a (default) interactive mode, offering a text user interface (TUI) that allows you to navigate through you Ansible content and discover available actions. It also allows you to run your playbooks in non-interactive (aka stdout) mode.
3.  Execution Environment support comparison:
    -   ansible-playbook has to run playbooks via some type of local Python environment (e.g., using your system Python or a Python virtualenv).
    -   Ansible Navigator supports execution environments, which are containerized environments that isolate Ansible execution. This ensures a consistent environment for running playbooks and reduces the risk of conflicts between dependencies.
4.  Extensibility:
    -   ansible-playbook is almost 100% focused on executing playbooks, and you sometimes end up having to use other ansible-* tools to perform other pretty common related tasks.
    -   Ansible Navigator provides additional features, such as browsing documentation, visualizing inventory, and managing collections, all of which makes it a more versatile tool for working with Ansible content.

Ansible Navigator was really created to address some limitations of the traditional Ansible CLI tools, and it provides you with a more efficient way to work with all things Ansible:

-   Improves the user experience by providing a more interactive look and feel.
-   Enhances the average discoverability of Ansible content and available actions.
-   Simplifies the usage of execution environments, allowing you to work with containerized Ansible instances. This point is highly relevant for AAP customers, as there is no equivalent functionality available to you with ansible-playbook.

To go a bit deeper on discoverability, this means being able to effortlessly explore and find Ansible content, actions, and information, all within the Ansible Navigator TUI. Some examples in practice:

1.  Exploring playbooks and roles: You can browse through your playbooks and roles, making it easier to find specific automation tasks or examine the structure of your Ansible content.
2.  Browsing collections: Ansible Navigator allows you to explore Ansible collections. You can navigate through the collections, view the included content, and see ways to use them in your own automations.
3.  Viewing documentation: Ansible Navigator enables you to view documentation for modules, roles, and plugins, all within in the TUI.
4.  Visualizing inventory: You can easily visualize your inventory in Ansible Navigator, which provides an organized view of hosts and groups. You’ll find that this makes it easier to discover the structure of the inventory and understand how hosts and groups relate to each other.
5.  Listing available actions: When using the (default) interactive mode, Ansible Navigator displays a list of available actions that you can take, such as running a playbook, examining a role, or exploring a collection. Inarguably, this feature enhances increases your awareness of “the art of the possible” for the particular Ansible content you are working with, by providing an at-your-fingertips overview of possible actions and guiding you in your interactions with custom code especially.

## Steps

1.  Install `podman`.
2.  Install `ansible` and `ansible-navigator` in a Python virtualenv.
3.  Create an `inventory` file.
4.  Create an `ansible-navigator.yml` config file.
5.  Create a `test.yml` playbook.
6.  Examples.

These steps assume you are running a RHEL-based system, and they maximize the likelihood you will be running a supported version of Python for your Ansible* pip installs.

## Install podman

```shell
$ sudo yum install podman -y
```

## Install `ansible` and `ansible-navigator` in a Python virtualenv

```shell
cd ~
sudo yum install python39 -y
python3.9 -m venv navdemo
source navdemo/bin/activate
pip3 install --upgrade pip 
pip3 install ansible ansible-navigator
which ansible # SHOULD BE: ~/navdemo/bin/ansible
which ansible-navigator # SHOULD BE: ~/navdemo/bin/ansible-navigator
```

## Create an `inventory` file

A pretty simple test `~/inventory` file might look like:

```shell
(navdemo) [vagrant@rhel8 ~]$ cat inventory 
locahost ansible_connection=local

(navdemo) [vagrant@rhel8 ~]$ 
```

## Create an `ansible-navigator.yml` config file

Next let’s write an `~/ansible-navigator.yml` config file that will give us a good jumping off point to explore some key features of ansible-navigator in a moment (see more options [here](https://access.redhat.com/documentation/en-us/red_hat_ansible_automation_platform/2.3/html/ansible_navigator_creator_guide/assembly-settings-navigator_ansible-navigator)):

```yaml
# ansible-navigator.yml:
---
ansible-navigator:
  ansible:
    inventory:
      entries:
      - _test_inventory_static
#      - inventory
  execution-environment:
    container-engine: podman
    enabled: false
    image: quay.io/ansible/ansible-navigator-demo-ee:latest
  logging:
    level: debug
  playbook-artifact:
    enable: true
    save-as: playbook-artifacts/{playbook_name}-artifact-{ts_utc}.json
  # mode: stdout
```

And here’s an Ansible playbook we’ll call `~/test.yml`:

```yaml
# test.yml:
---
- name: Test Playbook
  hosts: all
  tasks:
    - name: Test ping
      ansible.builtin.ping:
      register: result

    - name: Print ping result
      ansible.builtin.debug:
        msg: "{{ result }}"
```

With setup out of the way, here are ten common Ansible-navigator commands:

1.  `ansible-navigator`: Launches Ansible-navigator in interactive mode, providing a text user interface (TUI) to explore your Ansible content. (and `ansible-navigator run test.yml` executes that playbook specifically.)
2.  `ansible-navigator run test.yml -m stdout`: Executes the specified playbook in non-interactive (stdout) mode, displaying the output directly in the terminal more like ansible-playbook would.
3.  `ansible-navigator inventory -i inventory`: Visualizes the specified inventory file, showing an organized view of hosts and groups.
4.  `ansible-navigator config`: Displays the current Ansible configuration settings, including values from environment variables, configuration files, and defaults.
5.  `ansible-navigator doc ansible.builtin.ping`: Shows the documentation for the specified module, including a description, available parameters, and usage examples.
6.  `ansible-navigator images`: Lists the available container images for execution environments, along with their details and status.
7.  `cat ~/ansible-navigator.log`: Displays the Ansible Navigator log, which contains information about the tool’s operation, including any errors or warnings.
8.  `ansible-navigator replay playbook-artifacts/test-artifact-2023-04-11T00\:20\:01.029398+00\:00.json`: “Replays” a previous ansible-navigator “run”.
9.  `ansible-navigator run test.yml -i inventory --eei ansible-navigator-demo-ee`: Specifies both an inventory and execution environment in a “run”.
10.  `ansible-navigator collections`: Lists all installed Ansible collections, including their name, version, and installation path (while some recent versions [appear to have a bug](https://github.com/ansible/ansible-navigator/issues/1482), the older stable 1.1.0 is still working OK and we have no reason to believe the functionality will not be retained going forward, so we are including it here).

The above commands cover a pretty wide range of Ansible Navigator features, allowing you to explore, manage, and execute your Ansible content quickly and effectively.

## References

- https://levelupla.io/a-blazingly-fast-ansible-navigator-tutorial/
- 
