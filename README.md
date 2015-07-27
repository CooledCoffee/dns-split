# 简介
由于众所周知的原因，我们访问很多国外网站的时候都需要使用VPN服务。
默认情况下，VPN连接上之后，域名解析相应地会切换到国外的DNS上。这会带来两个问题：

首先，国内站点的解析也需要通过国外的DNS来进行，速度很慢。

其次，有些站点（例如淘宝的CDN）使用国外DNS解析时，会解析到国外的IP上，导致图片加载非常慢。

在VPN上使用国内的DNS同样有问题，解析之后很多站点无法访问。

本项目的思路在于实现一个DNS代理服务，使用国外的DNS（目前使用谷歌的8.8.8.8）解析国外的域名，使用国内的DNS（目前使用阿里的223.5.5.5）解析国内的域名。
同时，对解析的结果进行缓存。

# 安装步骤 (Ubuntu 14.04)

1\. 安装python和相应的包

	sudo apt-get install python python-gevent python-pip
	sudo pip install dnslib

2\. 禁用dnsmasq

Ubuntu桌面版默认使用Network Manager来管理网络，并使用dnsmasq做DNS缓存。
为了避免端口冲突，我们需要禁用dnsmasq。

首先杀掉dnsmasq进程

	sudo pkill dnsmasq

然后修改Network Manager配置文件/etc/NetworkManager/NetworkManager.conf，
将“dns=dnsmasq”这一行注释掉，禁止dnsmasq自动启动。

最后重启Network Manager

	sudo restart network-manager

3\. 拷贝代码

	git clone git@github.com:CooledCoffee/dns-split.git
	mkdir /srv
	mv dns-split /srv

4\. 启动服务

手动方式：

	sudo python /srv/dns-split/dns.py

自动方式：

	sudo cp dns-split /etc/init.d
	sudo update-rc.d dns-split defaults
	sudo service dns-split start
