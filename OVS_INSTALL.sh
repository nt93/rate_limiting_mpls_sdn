apt-get update

apt-get install -y git automake autoconf gcc uml-utilities libtool build-essential git pkg-config linux-headers-`uname -r`
sleep 2
wget http://openvswitch.org/releases/openvswitch-2.7.0.tar.gz

tar -zxvf openvswitch-2.7.0.tar.gz
cd /root/openvswitch-2.7.0/
./boot.sh
./configure --with-linux=/lib/modules/`uname -r`/build
make

make install
modprobe openvswitch

touch /usr/local/etc/ovs-vswitchd.conf
mkdir -p /usr/local/etc/openvswitch

cd /root/openvswitch-2.7.0/
ovsdb-tool create /usr/local/etc/openvswitch/conf.db vswitchd/vswitch.ovsschema
mkdir /etc/openvswitch

ovsdb-server --remote=punix:/usr/local/var/run/openvswitch/db.sock     --remote=db:Open_vSwitch,Open_vSwitch,manager_options    --private-key=db:Open_vSwitch,SSL,private_key    --certificate=db:Open_vSwitch,SSL,certificate    --bootstrap-ca-cert=db:Open_vSwitch,SSL,ca_cert    --pidfile --detach --log-file

ovs-vsctl --no-wait init
ovs-vswitchd --pidfile --detach --log-file

ovs-vsctl show
ovs-vsctl add-br br0
ovs-vsctl set Bridge br0 protocol=OpenFlow14
ifconfig br0 up

ovs-vsctl set-fail-mode br0 secure
#ovs-vsctl set-controller br-int tcp:192.168.0.1:6633

