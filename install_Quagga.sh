#!/bin/bash

# Configurations variables here
log_file="/var/log/install_mpls.log"
loopback_addr=1.1.1.1

#
neighbour=("2.2.2.2" "3.3.3.3")
#<<<<<<<<<<<<<<<<<<<CHANGE LOOPBACK>>>>>>>>>>>>>>>>>>>>>>>>>>>


#create a log file
touch $log_file
echo $(date) "#" $(hostname) "Starting shell script">>$log_file

#set the root password
#echo root| passwd root --stdin
#passwd -u root

#check root access
if [ `whoami` != root ]; then
    echo "Please run this script as root or using sudo">>$log_file
    exit
fi

rm kernel4.4.tar.gz >/dev/null 2>&1

#Copy the lib folder for correct kernel on geni
echo "Fetching kernel4.4.tar.gz [/lib/module/4.4.0-31-generic]">>$log_file
wget http://www4.ncsu.edu/~dgupta9/kernel4.4.tar.gz>/dev/null >>$log_file 2>&1
if [ $? -eq 0 ]; then
    echo "Download successful">>$log_file
else
	echo "Failed to download kernal tar">>$log_file
	exit
fi
tar -zxvf kernel4.4.tar.gz -C /
if [ $? -eq 0 ]; then
    echo "Copy libraries successful">>$log_file
else
	echo "Failed to copy library folder">>$log_file
	exit
fi

#update the kernel
apt-get -y update
apt-get -y upgrade

#load mpls modules
modprobe mpls_router
modprobe mpls_gso
modprobe mpls_iptunnel

#check modules loaded successfuly
lsmod|grep -q 'mpls_router'
ch1=$?
lsmod|grep -q 'mpls_gso'
ch2=$?
lsmod|grep -q 'mpls_iptunnel'
ch3=$?

if [[ ($ch1 -eq 0) && ($ch2 -eq 0) && ($ch3 -eq 0) ]]; then
    echo "Copy libraries successful">>$log_file
else
	echo "Failed to load library">>$log_file
	exit
fi


#add number of mpls label tables rows as 1000
#config from [http://pieknywidok.blogspot.com.es/2015/12/mpls-testbed-on-ubuntu-linux-with.html]
echo "setting mpls labels count and enabling on each interface">>$log_file
sysctl -w net.mpls.platform_labels=1000

#enable mpls on each interface
#get the list of interfaces [https://superuser.com/questions/203272/list-only-the-device-names-of-all-available-network-interfaces]
iflist=$(ifconfig -a | sed 's/[ \t].*//;/^$/d')
for i in $iflist
do
	sysctl -w net.mpls.conf.$i.input=1
done

echo ""

#enable ip forwarding
echo "Setting ip_forwarding on each interface">>$log_file
echo "1" > /proc/sys/net/ipv4/ip_forward
echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf

echo "Environment Setup Done">>$log_file
###########################  Quagga #####################

apt-get install -y autoconf automake texinfo libtool git libreadline-gplv2-dev build-essential >>$log_file 2>&1
sleep 3
git clone https://github.com/rwestphal/quagga-ldpd.git >>$log_file 2>&1
cd $PWD/quagga-ldpd/
./bootstrap.sh \#autoreconf -i >>$log_file 2>&1
./configure --enable-tcp-zebra --enable-mpls --enable-ldpd --sysconfdir=/etc/quagga --localstatedir=/var/run >>$log_file 2>&1
./bootstrap.sh \#autoreconf -i >>$log_file 2>&1
./configure --enable-tcp-zebra --enable-mpls --enable-ldpd --sysconfdir=/etc/quagga --localstatedir=/var/run >>$log_file 2>&1
echo "Running make of Quagga-LDPD">>$log_file
make >>$log_file 2>&1
sleep 3
./bootstrap.sh \#autoreconf -i >>$log_file 2>&1
./configure --enable-tcp-zebra --enable-mpls --enable-ldpd --sysconfdir=/etc/quagga --localstatedir=/var/run >>$log_file 2>&1
make >>$log_file 2>&1
make install >>$log_file 2>&1
if [ $? -eq 0 ]; then
	echo "Make successful of Quagga-LDPD, Now installing">>$log_file
else
	echo "Make failed, check logs">>$log_file
	exit
fi

ls /etc/quagga/
ldconfig /usr/local/lib
if [ $? -eq 0 ]; then
	echo "Successfully configured shared library">>$log_file
else
	echo "Failed to configure shared library">>$log_file
	exit
fi

useradd quagga>>$log_file
chown -R quagga.quagga /etc/quagga
touch /var/run/zebra.pid
chmod 755 /var/run/zebra.pid
chown quagga.quagga /var/run/zebra.pid
touch /var/run/ospfd.pid
chmod 755 /var/run/ospfd.pid
chown quagga.quagga /var/run/ospfd.pid
touch /var/run/ldpd.pid 
chmod 755 /var/run/ldpd.pid 
chown quagga.quagga /var/run/ldpd.pid
touch /var/run/ldpd.vty 
chmod 755 /var/run/ldpd.vty 
chown quagga.quagga /var/run/ldpd.vty 
chmod 777 /var/run
cp /etc/quagga/zebra.conf.sample /etc/quagga/zebra.conf 
cp /etc/quagga/ospfd.conf.sample /etc/quagga/ospfd.conf
cp /etc/quagga/ldpd.conf.sample /etc/quagga/ldpd.conf

echo "####################################################">>$log_file
echo "#############  Quagga Setup Completed  #############">>$log_file
echo "####################################################">>$log_file


# Add settings
echo -e "\nAdding configurations">>$log_file
ip link add name lo1 type dummy>>$log_file 2>&1
ip link set dev lo1 up>>$log_file 2>&1
ip addr add $loopback_addr dev lo1>>$log_file 2>&1

#configure ospfd
if_list=($(ls -d /sys/class/net/eth[1-9] |sed 's/.*\(eth[0-9]\)/\1/'))

echo -e "router ospf">>/etc/quagga/ospfd.conf
echo -e " network "$loopback_addr"/32 area 0">>/etc/quagga/ospfd.conf
for i in "${if_list[@]}"
do
if_ip=$(/sbin/ifconfig $i | grep 'inet addr:' | cut -d: -f2|awk '{print $1}')
if_nw_ip=$(echo $if_ip|sed -e "s/\([0-9]*.[0-9]*.[0-9]*.\)./\10/g")
echo -e " network "$if_nw_ip"/24 area 0">>/etc/quagga/ospfd.conf
done
#echo -e "  mpls-te\n  mpls-te router-address "$loopback_addr>>/etc/quagga/ospfd.conf

#configure mpls
#MODIFY as needed
echo -e "debug mpls ldp messages recv\ndebug mpls ldp messages sent">/etc/quagga/ldpd.conf
echo -e "debug mpls ldp zebra\n!\nmpls ldp\n router-id "$loopback_addr>>/etc/quagga/ldpd.conf
echo -e " dual-stack transport-connection prefer ipv4\n dual-stack cisco-interop">>/etc/quagga/ldpd.conf
for i in "${neighbour[@]}"
do
echo -e " neighbor "$i" password testmpls">>/etc/quagga/ldpd.conf
done
echo -e " !\n address-family ipv4">>/etc/quagga/ldpd.conf
echo -e "  discovery transport-address "$loopback_addr"\n  !">>/etc/quagga/ldpd.conf
if_list=($(ls -d /sys/class/net/eth[1-9] |sed 's/.*\(eth[0-9]\)/\1/'))
for i in "${if_list[@]}"
do
echo -e "  interface "$i>>/etc/quagga/ldpd.conf
done
echo -e "  !\n !\n!">>/etc/quagga/ldpd.conf

zebra -d -f /etc/quagga/zebra.conf 
ospfd -d -f /etc/quagga/ospfd.conf 
ldpd -d -f /etc/quagga/ldpd.conf

