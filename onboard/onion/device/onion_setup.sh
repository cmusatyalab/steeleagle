#!/bin/ash

# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

clear
echo "======================================"
echo "|     Automated WireGuard Script     |"
echo "|        Named Peers with IDs        |"
echo "======================================"
# Define Variables
echo -n "Defining variables... "
export LAN="wg0"
export interface="10.8.0"
export public_lte_ip="162.x.x.x"
export peer_ID="1" # The ID number to start from
export peer_IP="2" # The IP address to start from
export WG_${LAN}_server_port="51820"
export WG_${LAN}_server_IP="${interface}.1"
export WG_${LAN}_server_firewall_zone="${LAN}"
export quantity="4" # Change the number '4' to any number of peers you would like to create
export user_1="Alpha"
export user_2="Bravo"
export user_3="Charlie"
export user_4="Delta"
echo "Done"
 
# Create directories
echo -n "Creating directories and pre-defining permissions on those directories... "
mkdir -p /etc/wireguard/networks/${LAN}/peers
echo "Done"
 
# Remove pre-existing WireGuard interface
echo -n "Removing pre-existing WireGuard interface... "
uci del network.wg_${LAN} >/dev/null 2>&1
echo "Done"
 
# Generate WireGuard server keys
echo -n "Generating WireGuard server keys for '${LAN}' network... "
wg genkey | tee "/etc/wireguard/networks/${LAN}/${LAN}_server_private.key" | wg pubkey | tee "/etc/wireguard/networks/${LAN}/${LAN}_server_public.key" >/dev/null 2>&1
echo "Done"
 
echo -n "Rename firewall.@zone[0] to lan and firewall.@zone[1] to wan... "
uci rename firewall.@zone[0]="lan"
uci rename firewall.@zone[1]="wan"
echo "Done"
 
# Create WireGuard interface for 'LAN' network
echo -n "Creating WireGuard interface for '${LAN}' network... "
eval "server_port=\${WG_${LAN}_server_port}"
eval "server_IP=\${WG_${LAN}_server_IP}"
eval "firewall_zone=\${WG_${LAN}_server_firewall_zone}"
uci set network.wg_${LAN}=interface
uci set network.wg_${LAN}.proto='wireguard'
uci set network.wg_${LAN}.private_key="$(cat /etc/wireguard/networks/${LAN}/${LAN}_server_private.key)"
uci set network.wg_${LAN}.listen_port="${server_port}"
uci add_list network.wg_${LAN}.addresses="${server_IP}/24"
uci set firewall.${LAN}.network="${firewall_zone} wg_${firewall_zone}"
uci set network.wg_${LAN}.mtu='1420'
echo "Done"
 
# Add firewall rule
echo -n "Adding firewall rule for '${LAN}' network... "
uci set firewall.wg="rule"
uci set firewall.wg.name="Allow-WireGuard-${LAN}"
uci set firewall.wg.src="wan"
uci set firewall.wg.dest_port="${server_port}"
uci set firewall.wg.proto="udp"
uci set firewall.wg.target="ACCEPT"
echo "Done"
 
# Remove existing peers
echo -n "Removing pre-existing peers... "
while uci -q delete network.@wireguard_wg_${LAN}[0]; do :; done
rm -R /etc/wireguard/networks/${LAN}/peers/* >/dev/null 2>&1
echo "Done"
 
# Loop
n="0"
while [ "$n" -lt ${quantity} ] ; 
do
 
for username in ${user_1} ${user_2} ${user_3} ${user_4}
do
 
# Configure variables
eval "peer_ID_${username}=${peer_ID}"
eval "peer_IP_${username}=${peer_IP}"
 
eval "peer_ID=\${peer_ID_${username}}"
eval "peer_IP=\${peer_IP_${username}}"
 
eval "server_port=\${WG_${LAN}_server_port}"
eval "server_IP=\${WG_${LAN}_server_IP}"
 
echo ""
# Create directory for storing peers
echo -n "Creating directory for peer '${peer_ID}_${LAN}_${username}'... " 
mkdir -p "/etc/wireguard/networks/${LAN}/peers/${peer_ID}_${LAN}_${username}"
echo "Done"
 
# Generate peer keys
echo -n "Generating peer keys for '${peer_ID}_${LAN}_${username}'... " 
wg genkey | tee "/etc/wireguard/networks/${LAN}/peers/${peer_ID}_${LAN}_${username}/${peer_ID}_${LAN}_${username}_private.key" | wg pubkey | tee "/etc/wireguard/networks/${LAN}/peers/${peer_ID}_${LAN}_${username}/${peer_ID}_${LAN}_${username}_public.key" >/dev/null 2>&1
echo "Done"
 
# Generate Pre-shared key
echo -n "Generating peer PSK for '${peer_ID}_${LAN}_${username}'... " 
wg genpsk | tee "/etc/wireguard/networks/${LAN}/peers/${peer_ID}_${LAN}_${username}/${peer_ID}_${LAN}_${username}.psk" >/dev/null 2>&1
echo "Done"
 
# Add peer to server 
echo -n "Adding '${peer_ID}_${LAN}_${username}' to WireGuard server... " 
uci add network wireguard_wg_${LAN} >/dev/null 2>&1
uci set network.@wireguard_wg_${LAN}[-1].public_key="$(cat /etc/wireguard/networks/${LAN}/peers/${peer_ID}_${LAN}_${username}/${peer_ID}_${LAN}_${username}_public.key)"
uci set network.@wireguard_wg_${LAN}[-1].preshared_key="$(cat /etc/wireguard/networks/${LAN}/peers/${peer_ID}_${LAN}_${username}/${peer_ID}_${LAN}_${username}.psk)"
uci set network.@wireguard_wg_${LAN}[-1].description="${peer_ID}_${LAN}_${username}"
uci add_list network.@wireguard_wg_${LAN}[-1].allowed_ips="${interface}.${peer_IP}/32"
uci set network.@wireguard_wg_${LAN}[-1].route_allowed_ips='1'
uci set network.@wireguard_wg_${LAN}[-1].persistent_keepalive='25'
echo "Done"

# Create DNAT rules
echo -n "Adding DNAT for '${peer_ID}_${LAN}_${username}..."
rule_name=$(uci add firewall redirect)
uci batch << EOI
set firewall.$rule_name.dest='vpn'
set firewall.$rule_name.dest_ip='${interface}.${peer_IP}'
set firewall.$rule_name.dest_port='55004'
set firewall.$rule_name.src='drone'
set firewall.$rule_name.src_dport='55004'
set firewall.$rule_name.proto='udp'
set firewall.$rule_name.target='DNAT'
set firewall.$rule_name.name='DNAT drone to vpn for udp traffic'
EOI

echo "Done"

# Create peer configuration
echo -n "Creating config for '${peer_ID}_${LAN}_${username}'... "
cat <<-EOF > "/etc/wireguard/networks/${LAN}/peers/${peer_ID}_${LAN}_${username}/${peer_ID}_${LAN}_${username}.conf"
[Interface]
Address = ${interface}.${peer_IP}/32
PrivateKey = $(cat /etc/wireguard/networks/${LAN}/peers/${peer_ID}_${LAN}_${username}/${peer_ID}_${LAN}_${username}_private.key) # Peer's private key
 
[Peer]
PublicKey = $(cat /etc/wireguard/networks/${LAN}/${LAN}_server_public.key) # Server's public key
PresharedKey = $(cat /etc/wireguard/networks/${LAN}/peers/${peer_ID}_${LAN}_${username}/${peer_ID}_${LAN}_${username}.psk) # Peer's pre-shared key
PersistentKeepalive = 25
AllowedIPs = 192.168.42.1/24, ${interface}.1/24 
Endpoint = ${public_lte_ip}:${server_port}
EOF
echo "Done"
 
# Increment variables by '1'
peer_ID=$((peer_ID+1))
peer_IP=$((peer_IP+1))
n=$((n+1))
done
done

echo -n "Configuring logging..."
uci set system.log_file='/var/log/uci.log'
uci set system.log_remote='0'
echo "Done"

echo -n "Adding firewall zones/rules..."


name=$(uci add firewall zone) 
uci batch << EOI
set firewall.$name.output='ACCEPT'
set firewall.$name.input='ACCEPT'
set firewall.$name.forward='ACCEPT'
set firewall.$name.network='wg_wg0'
set firewall.$name.name='vpn'
EOI

name=$(uci add firewall zone)
uci batch << EOI
set firewall.$name.output='ACCEPT'
set firewall.$name.input='ACCEPT'
set firewall.$name.forward='ACCEPT'
set firewall.$name.network='wwan'
set firewall.$name.name='drone'
EOI

rule_name=$(uci add firewall rule)
uci batch << EOI
set firewall.$rule_name.dest='drone'
set firewall.$rule_name.src='vpn'
set firewall.$rule_name.proto='all'
set firewall.$rule_name.target='ACCEPT'
set firewall.$rule_name.name='Allow vpn to drone zone'
EOI
echo "Done"

 
# Commit UCI changes
echo -en "\nCommiting changes... "
uci commit
echo "Done"
 
# Restart WireGuard interface
echo -en "\nRestarting WireGuard interface... "
ifup wg_${LAN}
echo "Done"
 
# Restart firewall
echo -en "\nRestarting firewall... "
/etc/init.d/firewall restart >/dev/null 2>&1
echo "Done"
