################################################
#   RYU PSEUDOMAC
#   Control bandwidth allocation to flow and route data using mac address
#   Required OpenFlow 1.4 support from switch
#
#   Part of code copied from Github "osrg/ryu" [https://github.com/osrg/ryu/blob/master/ryu/app/simple_switch_14.py
#   [https://sdn-lab.com/2014/12/31/topology-discovery-with-ryu/]
################################################
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import arp
from ryu.ofproto import ofproto_v1_4
from ryu.ofproto import ether

from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link

import random

destip_psuedoMap = {}

class RyuPseudomacApp(app_manager.RyuApp):
    # Main class for ryu application

    #Supports version 1.4 of OVS
    OFP_VERSIONS = [ofproto_v1_4.OFP_VERSION]

    def __init__(self,*args, **kwargs):
        """
        Constructor
        :param args: non-keyword arguments
        :param kwargs: keyword arguments
        """
        super(RyuPseudomacApp,self).__init__(*args,**kwargs)
        #Contains the mapping of flow ('SourceIP','DestinationIP') to rate associated
        self.serviceMap = {
            ("1.1.1.2", "2.2.2.3"): 1,
            ("1.1.1.2", "2.2.2.3"): 3
        }

        # Contains the mapping of flow ('SourceIP','DestinationIP') to pseudomac address assigned
        self.pseudoMap = {}

        # TODO: check if we create path dynamically
        self.OVSGraph = {1:{2:2,3:1},2:{1:1,3:2},3:{1:1,2:2}}

        # store host mac address which ovs's
        self.mac_to_port = {}

        # store the datapath objects of each OVS
        self.ovs_datapath = {}

        self.generatedMac = []
        self.hexletter = '0123456789abcdef'

        # [actual destination IP] => pseudo mac alloted before
        self.routes={
            ("1.1.1.2", "2.2.2.3"):[1, 2, 3],
            ("2.2.2.3", "1.1.1.2"):[3, 1]
        }

        #store maping of each IP address to its mac address, datapath and datapath's connected port
        self.destip_datapath={}

    def add_flow_rate(self,sip,dip,rate):
        """
        Add the entry of source IP
        :param sip: source IP
        :param dip: destination IP
        :param rate: bandwidth in bits/sec eg 1000 for 1kbps
        :return: None
        """
        self.serviceMap[(sip,dip)]=rate

    def get_flow_rate(self,sid,dip):
        """
        :param sid: source IP for flow
        :param dip: destination IP for flow
        :return: rate/bandwidth in bits/sec  OR 0 to denote no bandwidth allocated
        """
        tup = (sid,dip)
        if tup in self.serviceMap:
            return self.serviceMap[tup]
        else:
            return 100000# 100kbps

    def get_pseudomac(self,sid,dip):
        """

        :param sid: source IP for flow
        :param dip: destination IP for flow
        :return: Pseudomac address assigned to tuple
        """
        tup = (sid, dip)
        if tup in self.pseudoMap:
            return self.pseudoMap[tup]
        else:
            self.pseudoMap[tup]=self.generate_random_mac()
            return self.pseudoMap[tup]

    def set_openflow_ovs(self,datapath,match,action,priority_val,timeout=300):
        """
        Adds the flow rule on ovs
        :return:
        """
        protocol=datapath.ofproto
        parser = datapath.ofproto_parser
        #instruction list
        instruction=[]
        instruction.append(parser.OFPInstructionActions(protocol.OFPIT_APPLY_ACTIONS,
                                             action))
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority_val,hard_timeout=timeout,
                                match=match, instructions=instruction)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def initialize_ovs_rule(self,ev):
        """
        Add a flow rule such that when no rule matches on OVS, query controller
        :param ev:
        :return:
        """
        datapath = ev.msg.datapath
        self.ovs_datapath[datapath.id]=datapath
        #packet_in_pkt = packet.Packet(ev.msg.data)
        match = datapath.ofproto_parser.OFPMatch()
        actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_CONTROLLER,
                                                           datapath.ofproto.OFPCML_NO_BUFFER)]
        self.set_openflow_ovs(datapath, match, actions,0,0)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def ovs_packetin_handler(self, ev):
        """
        Handle arp request for resource
        :param ev:
        :return:
        """
        global destip_psuedoMap
        msg = ev.msg
        packet_in_pkt = packet.Packet(msg.data)

        #datapath object for the request
        datapath = msg.datapath

        #in port for the datapath
        in_port = msg.match['in_port']
        eth = packet_in_pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return

        #self.logger.info("\n\nDATAPATH ID : " + self.convert_int_hex(datapath.id))
        #self.logger.info("Rev")

        #get the object for OpenFlow protocol constants
        ofproto = datapath.ofproto

        #get the object for OpenFlow protocol parser
        ofproto_parser = datapath.ofproto_parser

        #check for packet type 'arp' to create data path and learn hosts
        for p in packet_in_pkt:
            if p.protocol_name=='arp':

                arpRequest = packet_in_pkt.get_protocols(arp.arp)[0]

                #store the mac address of the host along with which datapath and port connected to
                self.mac_to_port.setdefault(eth.src, {})
                self.mac_to_port[arpRequest.src_mac][datapath.id]=in_port
                self.destip_datapath[arpRequest.src_ip]=(arpRequest.src_mac,datapath,in_port)

                self.logger.info("Got ARP request from Sourece IP [%s] for  Destination IP [%s] ",arpRequest.src_ip,arpRequest.dst_ip)

                # handle the special case where destination host mac address not known
                if arpRequest.src_ip in destip_psuedoMap:
                    dst_mac = arpRequest.src_mac
                    #lastDPID = self.routes[(arpRequest.src_ip,arpRequest.dst_ip)][-1]
                    #lastDP = self.ovs_datapath[lastDPID]
                    self.logger.info("Captured destination mac needed for ip %s as %s",arpRequest.src_ip,dst_mac)
                    match = ofproto_parser.OFPMatch(eth_dst=destip_psuedoMap[arpRequest.src_ip])
                    actions = [ofproto_parser.OFPActionSetField(eth_dst=dst_mac), ofproto_parser.OFPActionOutput(in_port)]
                    self.set_openflow_ovs(datapath, match, actions, 1)
                    del destip_psuedoMap[arpRequest.src_ip]
                    return


                flow_route = self.routes[(arpRequest.src_ip,arpRequest.dst_ip)]
                rate=self.get_flow_rate(arpRequest.src_ip,arpRequest.dst_ip)

                #create a random mac address
                pseudomac = self.get_pseudomac(arpRequest.src_ip,arpRequest.dst_ip)
                self.logger.info("Generated psuedomac for destination host IP [%s] as [%s]",arpRequest.dst_ip,pseudomac)

                #create artificial arp request
                arpReply = arp.arp(hwtype=1, proto=0x0800, hlen=6, plen=4, opcode=2, src_mac=pseudomac,
                            src_ip=arpRequest.dst_ip,dst_mac=arpRequest.src_mac, dst_ip=arpRequest.src_ip)

                #create ethernet headers
                ethReply = ethernet.ethernet(arpRequest.src_mac, pseudomac, ether.ETH_TYPE_ARP)
                artificialPacket = packet.Packet()
                artificialPacket.add_protocol(ethReply)
                artificialPacket.add_protocol(arpReply)
                artificialPacket.serialize()

                # action to send the artificial arp packet via same port on datapath connected to host
                actions = [datapath.ofproto_parser.OFPActionOutput(msg.match['in_port'], 0)]
                out = datapath.ofproto_parser.OFPPacketOut(datapath=datapath, buffer_id=0xffffffff,
                                                           in_port=datapath.ofproto.OFPP_CONTROLLER,
                                                           actions=actions, data=artificialPacket.data)
                self.logger.info("Sent the artificial ARP reply %s",str(arpReply))



                # Now fetch the actual mac address of destination IP if not known
                if arpRequest.dst_ip not in self.destip_datapath:
                    # add entry in self.destip_psuedoMap
                    destip_psuedoMap[arpRequest.dst_ip] = pseudomac

                    lastDPID = flow_route[-1]
                    lastDP = self.ovs_datapath[lastDPID]

                    # ASSUMPTION: All the subnet have *.*.*.1 address assigned to interface of OVS connecting to host
                    lastDPIP = arpRequest.dst_ip.split(".")
                    lastDPIP = ".".join(lastDPIP[:3])+".1"

                    arpRequest2 = arp.arp(hwtype=1, proto=0x0800, hlen=6, plen=4, opcode=1, src_mac=arpRequest.src_mac,
                                       src_ip=lastDPIP, dst_mac='00:00:00:00:00:00', dst_ip=arpRequest.dst_ip)
                    ethRequest2 = ethernet.ethernet('ff:ff:ff:ff:ff:ff', pseudomac, ether.ETH_TYPE_ARP)
                    artificialPacket2 = packet.Packet()
                    artificialPacket2.add_protocol(ethRequest2)
                    artificialPacket2.add_protocol(arpRequest2)
                    artificialPacket2.serialize()
                    actions2 = [lastDP.ofproto_parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    out2 = lastDP.ofproto_parser.OFPPacketOut(datapath=lastDP, buffer_id=0xffffffff,
                                                               in_port=lastDP.ofproto.OFPP_CONTROLLER,
                                                               actions=actions2, data=artificialPacket2.data)
                    lastDP.send_msg(out2)
                    self.logger.info("Send the artificial ARP request to destination IP [%s] as [%s]",arpRequest.dst_ip,arpRequest2)
                else:
                    #set the swap of pseudo mac address with correct destination mac address
                    dst_datapath = self.destip_datapath[arpRequest.dst_ip][1]
                    match = ofproto_parser.OFPMatch(eth_dst=pseudomac)
                    actions = [ofproto_parser.OFPActionSetField(eth_dst=self.destip_datapath[arpRequest.dst_ip][0]),
                               ofproto_parser.OFPActionOutput(in_port)]
                    self.set_openflow_ovs(dst_datapath, match, actions, 1)




                # now add openflow rules on each OVS



                #INSTALL rule for pseudomac on each intermediate routers
                #SPECIAL CASE
                #check if the destination is just 1 HOP
                if(len(flow_route))==1:
                    pass
                else:
                    for i in range(len(flow_route)-1):
                        tempDP = self.ovs_datapath[flow_route[i]]
                        out_port = self.OVSGraph[flow_route[i]][flow_route[i+1]]
                        match = ofproto_parser.OFPMatch(eth_dst=pseudomac,in_port=in_port)
                        actions = [ofproto_parser.OFPActionOutput(out_port)]
                        if i==0:
                            #modify the out_port for ingress switch
                            actions = [ofproto_parser.OFPActionSetQueue(str(out_port)+str(rate))]

                        in_port = self.OVSGraph[flow_route[i+1]][flow_route[i]]
                        self.set_openflow_ovs(tempDP, match, actions, 1)

                #send the arp reply with pseudomac address to ingress switch
                datapath.send_msg(out)
                self.logger.info("Sent the pseudomac to source IP [%s]",arpRequest.src_ip)

    def generate_random_mac(self):
        """
        generates a random mac address and ensures that it is unique
        :return: 'xx-xx-xx-xx-xx-xx' string containing mac address
        """
        target=random.choice(self.hexletter) + random.choice(self.hexletter)
        target='f8-ee-c3-6d-86-'+target
        while target in self.generatedMac:
            target = random.choice(self.hexletter) + random.choice(self.hexletter)
            target = 'f8-ee-c3-6d-86-' + target
        return target

    @set_ev_cls(event.EventSwitchEnter)
    def get_topology_data(self, ev):
        # modify /usr/local/lib/python2.7/dist-packages/ryu/lib/packet/lldp.py 'LLDP_MAC_NEAREST_BRIDGE = 'ff:ff:ff:ff:ff:ff'
        switch_list = get_switch(self, None)
        self.switches = [switch.dp.id for switch in switch_list]

        for sw in self.switches:
            links_list = get_link(self, None)
            for link in links_list:
                #self.logger.info(link)
                self.OVSGraph.setdefault(link.src.dpid,{})
                self.OVSGraph.setdefault(link.dst.dpid, {})
                self.OVSGraph[link.src.dpid][link.dst.dpid]=link.src.port_no
                self.OVSGraph[link.dst.dpid][link.src.dpid] = link.dst.port_no

    def convert_int_hex(self,int_val):
        """

        :param int: integer format of ovs 's datapath
        :return: hex value as displayed in ovs-vsctl get Bridge br0 other_config:datapath-id
        """
        "Note: Set the datapath id -> ovs-vsctl set Brige br0 other_config:datapath-id=<DATAPATH ID>"
        return str(hex(int(int_val))[2:].zfill(16))



