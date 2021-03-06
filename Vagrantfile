# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  if Vagrant.has_plugin?("vagrant-proxyconf")
    config.proxy.http     = "http://proxy.ifmo.ru:3128"
    config.proxy.no_proxy = "localhost,127.0.0.1,127.0.1.1,10.141.141.10,192.168.13.132,192.168.13.133,"
  end

  config.vm.box = "mesos-demo"
  # config.vm.box_url = "http://downloads.mesosphere.io/demo/mesos-demo.box"

  # Create a private network, which allows host-only access to the machine
  # using a specific IP.
  config.vm.network :private_network, ip: "10.141.141.10"
  config.vm.network :public_network, ip: "192.168.92.5"

  # Enable agent forwarding.
  config.ssh.forward_agent = true

  # Share an additional folder to the guest VM. The first argument is
  # the path on the host to the actual folder. The second argument is
  # the path on the guest to mount the folder. And the optional third
  # argument is a set of non-required options.
  config.vm.synced_folder ".", "/vagrant", :disabled => true
  config.vm.synced_folder "./", "/home/vagrant/hostfiles"

  # Provider-specific configuration
  config.vm.provider :virtualbox do |vb|
    vb.customize ["modifyvm", :id, "--ioapic", "on"]
    vb.customize ["modifyvm", :id, "--cpus", "2"]
    vb.customize ["modifyvm", :id, "--memory", "2048"]
  end
  
   config.vm.provision "shell" do |s|
        dns_server = "if ! grep -q \'nameserver 192.168.13.132\' /etc/resolvconf/resolv.conf.d/head; then echo 'nameserver 192.168.13.132'|tee --append /etc/resolvconf/resolv.conf.d/head; fi;resolvconf -u;"
		default_iface = "ip route change to default dev eth1;"
		hosts_file = "echo '127.0.0.1 localhost'|tee /etc/hosts;echo '192.168.92.5 mesos.vm mesos'|tee --append /etc/hosts;"
		#hosts_file = "echo '127.0.0.1 localhost'|tee /etc/hosts;echo '127.0.1.1 mesos.vm mesos'|tee --append /etc/hosts;"
	    s.inline = "#{hosts_file}#{dns_server}#{default_iface}"
        s.privileged = true
   end
  

end
