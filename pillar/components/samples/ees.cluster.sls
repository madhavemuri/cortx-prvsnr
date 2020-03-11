cluster:
  cluster_ip:
  type: ees                           # single/ees/ecs
  node_list:
    - eosnode-1
    - eosnode-2
  eosnode-1:
    hostname: eosnode-1
    is_primary: true
    network:
      pvt_nw_addr: 192.168.0.0
      nw_search: pun.seagate.com
      mgmt_nw:                  # Management network interfaces
        iface:
          - eth0
        ipaddr: 
        netmask: 255.255.0.0
      data_nw:                  # Data network interfaces
        iface: 
          - eth1
        ipaddr: 
        netmask: 255.255.0.0
      roaming_ip:
      gateway_ip:               # Gateway IP of network
    storage:
      metadata_device:                # Device for /var/mero and possibly SWAP
        - /dev/sdb
      data_devices:                   # Data device/LUN from storage enclosure
        - /dev/sdc
  eosnode-2:
    hostname: eosnode-2
    is_primary: false
    network:
      pvt_nw_addr: 192.168.0.0
      nw_search: pun.seagate.com
      mgmt_nw:                  # Management network interfaces
        iface:
          - eth0
        ipaddr: 
        netmask: 255.255.0.0
      data_nw:                  # Data network interfaces
        iface: 
          - eth1
        ipaddr: 
        netmask: 255.255.0.0
      roaming_ip:
      gateway_ip:               # Gateway IP of network
    storage:
      metadata_device:                # Device for /var/mero and possibly SWAP
        - /dev/sdb
      data_devices:                   # Data device/LUN from storage enclosure
        - /dev/sdc
  storage_enclosure:
    id: storage_node_1            # equivalent to fqdn for server node
    type: 5U84                    # Type of enclosure. E.g. 5U84/PODS
    controller:
      type: gallium               # Type of controller on storage node. E.g. gallium/indium/sati
      primary_mc:
        ip: 127.0.0.1
        port: 80
      secondary_mc:
        ip: 127.0.0.1
        port: 80
      user: user
      password: 'passwd'

