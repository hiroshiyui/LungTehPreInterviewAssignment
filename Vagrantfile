# -*- mode: ruby -*-
# vi: set ft=ruby :
#
# Reproducible Frappe (develop branch) development VM on VirtualBox.
#
#   vagrant up          # create the VM and provision it with Ansible
#   vagrant provision   # re-run the (idempotent) Ansible playbook
#
# Everything that affects the result is pinned: the box below, ansible-core
# in ansible/requirements.txt, and the rest (uv, Python, Node, frappe-bench,
# the exact frappe commit) in ansible/group_vars/all.yml.

Vagrant.require_version ">= 2.3.0"

BOX         = "bento/ubuntu-24.04"
BOX_VERSION = "202510.26.0"

VM_CPUS   = Integer(ENV.fetch("FRAPPE_VM_CPUS", 2))
VM_MEMORY = Integer(ENV.fetch("FRAPPE_VM_MEMORY", 4096))
WEB_PORT  = Integer(ENV.fetch("FRAPPE_HOST_PORT", 8000))

Vagrant.configure("2") do |config|
  config.vm.box              = BOX
  config.vm.box_version      = BOX_VERSION
  config.vm.box_check_update = false
  config.vm.hostname         = "frappe-dev"

  # Frappe web server (bench serve) and realtime (Socket.IO) server. In
  # developer mode the browser connects to the realtime server on the
  # page's host at socketio_port (9000), so that forward must stay 9000.
  config.vm.network "forwarded_port", guest: 8000, host: WEB_PORT, host_ip: "127.0.0.1"
  config.vm.network "forwarded_port", guest: 9000, host: 9000,     host_ip: "127.0.0.1"

  # The project directory is shared into the guest; the custom app in
  # apps/hr_cost is symlinked into the bench so edits on the host (or
  # DocType changes saved in the Desk UI in developer mode) land in this repo.
  config.vm.synced_folder ".", "/vagrant"

  config.vm.provider "virtualbox" do |vb|
    vb.name   = "frappe-dev"
    vb.cpus   = VM_CPUS
    vb.memory = VM_MEMORY
  end

  # Install a pinned ansible-core inside the guest, then run the playbook
  # there (ansible_local), so the host needs nothing but Vagrant + VirtualBox.
  config.vm.provision "bootstrap", type: "shell",
    path: "scripts/bootstrap-ansible.sh"

  config.vm.provision "ansible", type: "ansible_local" do |ansible|
    ansible.install            = false
    ansible.compatibility_mode = "2.0"
    ansible.provisioning_path  = "/vagrant/ansible"
    # Explicit, because Ansible ignores ansible.cfg in a world-writable cwd
    # (which VirtualBox shared folders are).
    ansible.config_file        = "/vagrant/ansible/ansible.cfg"
    ansible.playbook           = "site.yml"
    ansible.playbook_command   = "/opt/ansible/bin/ansible-playbook"
    ansible.extra_vars         = { "frappe_user" => "vagrant" }
    ansible.verbose            = ENV.fetch("ANSIBLE_VERBOSE", false)
  end
end
