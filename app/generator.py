import base64
import json
import urllib.parse
from typing import List, Dict, Any
from app.config import WS_PATH_VLESS, WS_PATH_TROJAN, PRESET_CLEAN_IPS, PRESET_FRAGMENT
from app.database import get_active_public_nodes

def generate_vless_link(user: Dict[str, Any], domain: str, clean_ip: str = None, preset: str = "iran") -> str:
    address = clean_ip if clean_ip else domain
    sni = domain
    host = domain
    port = 443
    path = WS_PATH_VLESS

    params = {
        "encryption": "none",
        "security": "tls",
        "type": "ws",
        "host": host,
        "path": path,
        "sni": sni,
        "fp": "chrome"
    }

    if preset == "iran":
        params["path"] = f"{path}?ed=2048"
        params["alpn"] = "h2,http/1.1"
        remark = f"Milijon-VL-IR-{'CleanIP' if clean_ip else 'Direct'}-{user['username']}"
    elif preset == "china":
        params["alpn"] = "h2,http/1.1"
        remark = f"Milijon-VL-CN-{'CDN' if clean_ip else 'Direct'}-{user['username']}"
    elif preset == "russia":
        params["alpn"] = "h2,http/1.1"
        remark = f"Milijon-VL-RU-{'CDN' if clean_ip else 'Direct'}-{user['username']}"
    else:
        remark = f"Milijon-VL-{user['username']}"

    query_str = urllib.parse.urlencode(params)
    return f"vless://{user['uuid']}@{address}:{port}?{query_str}#{urllib.parse.quote(remark)}"

def generate_trojan_link(user: Dict[str, Any], domain: str, clean_ip: str = None, preset: str = "iran") -> str:
    address = clean_ip if clean_ip else domain
    sni = domain
    host = domain
    port = 443
    path = WS_PATH_TROJAN

    params = {
        "security": "tls",
        "type": "ws",
        "host": host,
        "path": path,
        "sni": sni,
        "fp": "chrome"
    }

    if preset == "iran":
        params["alpn"] = "h2,http/1.1"
        remark = f"Milijon-TR-IR-{'CleanIP' if clean_ip else 'Direct'}-{user['username']}"
    elif preset == "china":
        params["alpn"] = "h2,http/1.1"
        remark = f"Milijon-TR-CN-{user['username']}"
    else:
        remark = f"Milijon-TR-{user['username']}"

    query_str = urllib.parse.urlencode(params)
    return f"trojan://{user['password']}@{address}:{port}?{query_str}#{urllib.parse.quote(remark)}"

def generate_vmess_link(user: Dict[str, Any], domain: str, clean_ip: str = None, preset: str = "iran") -> str:
    address = clean_ip if clean_ip else domain
    remark = f"Milijon-VMess-{'IR' if preset == 'iran' else 'Global'}-{user['username']}"

    vmess_obj = {
        "v": "2",
        "ps": remark,
        "add": address,
        "port": 443,
        "id": user["uuid"],
        "aid": 0,
        "scy": "auto",
        "net": "ws",
        "type": "none",
        "host": domain,
        "path": f"{WS_PATH_VLESS}?ed=2048" if preset == "iran" else WS_PATH_VLESS,
        "tls": "tls",
        "sni": domain,
        "alpn": "h2,http/1.1"
    }
    raw_json = json.dumps(vmess_obj, ensure_ascii=False)
    b64 = base64.b64encode(raw_json.encode('utf-8')).decode('utf-8')
    return f"vmess://{b64}"

def generate_all_links_for_user(user: Dict[str, Any], domain: str) -> List[str]:
    links = []
    preset = user.get("country_preset", "iran")
    clean_ips = PRESET_CLEAN_IPS.get(preset, PRESET_CLEAN_IPS["iran"])

    # 1. Personal Dedicated Nodes (Direct & Clean IP)
    links.append(generate_vless_link(user, domain, clean_ip=None, preset=preset))
    links.append(generate_trojan_link(user, domain, clean_ip=None, preset=preset))
    links.append(generate_vmess_link(user, domain, clean_ip=None, preset=preset))

    for i, ip in enumerate(clean_ips[:2]):
        links.append(generate_vless_link(user, domain, clean_ip=ip, preset=preset))
        links.append(generate_trojan_link(user, domain, clean_ip=ip, preset=preset))

    # 2. Harvested Healthy Public Nodes (Global DE, NL, US, FI, etc.)
    try:
        public_nodes = get_active_public_nodes(limit=15, max_ping=1500)
        for p_node in public_nodes:
            if p_node.get("raw_link"):
                links.append(p_node["raw_link"])
    except Exception:
        pass

    return links

def generate_base64_subscription(user: Dict[str, Any], domain: str) -> str:
    links = generate_all_links_for_user(user, domain)
    raw_sub = "\n".join(links)
    return base64.b64encode(raw_sub.encode('utf-8')).decode('utf-8')

def generate_clash_meta_yaml(user: Dict[str, Any], domain: str) -> str:
    preset = user.get("country_preset", "iran")
    clean_ip = PRESET_CLEAN_IPS.get(preset, ["104.16.132.229"])[0]

    # Personal dedicated proxies
    proxies_yaml = [
        f"""  - name: "Milijon-VLESS-CleanIP"
    type: vless
    server: {clean_ip}
    port: 443
    uuid: {user['uuid']}
    network: ws
    tls: true
    udp: true
    servername: {domain}
    client-fingerprint: chrome
    ws-opts:
      path: "{WS_PATH_VLESS}?ed=2048"
      headers:
        Host: {domain}""",
        f"""  - name: "Milijon-VLESS-Direct"
    type: vless
    server: {domain}
    port: 443
    uuid: {user['uuid']}
    network: ws
    tls: true
    udp: true
    servername: {domain}
    client-fingerprint: chrome
    ws-opts:
      path: "{WS_PATH_VLESS}"
      headers:
        Host: {domain}""",
        f"""  - name: "Milijon-Trojan-Direct"
    type: trojan
    server: {domain}
    port: 443
    password: {user['password']}
    network: ws
    tls: true
    udp: true
    sni: {domain}
    client-fingerprint: chrome
    ws-opts:
      path: "{WS_PATH_TROJAN}"
      headers:
        Host: {domain}"""
    ]

    proxy_names = ["Milijon-VLESS-CleanIP", "Milijon-VLESS-Direct", "Milijon-Trojan-Direct"]
    public_proxy_names = []

    # Harvested Public Nodes
    try:
        public_nodes = get_active_public_nodes(limit=25, max_ping=1500)
        for i, node in enumerate(public_nodes):
            clean_name = f"{node['flag']} {node['country_code']}-{node['protocol'].upper()}-{node['server']} ({node['ping_ms']}ms)"
            # Avoid duplicate proxy names in Clash
            clean_name = clean_name.replace('"', '')
            if clean_name in proxy_names:
                clean_name = f"{clean_name} #{i+1}"

            proto = node["protocol"].lower()
            if proto == "vless":
                proxies_yaml.append(f"""  - name: "{clean_name}"
    type: vless
    server: {node['server']}
    port: {node['port']}
    uuid: {node['uuid_or_key']}
    network: {node.get('network', 'ws')}
    tls: {str(node.get('security') == 'tls').lower()}
    udp: true
    servername: {node.get('sni') or node['server']}
    client-fingerprint: chrome
    ws-opts:
      path: "{node.get('path', '/')}"
      headers:
        Host: {node.get('host') or node['server']}""")
                public_proxy_names.append(clean_name)

            elif proto == "trojan":
                proxies_yaml.append(f"""  - name: "{clean_name}"
    type: trojan
    server: {node['server']}
    port: {node['port']}
    password: {node['uuid_or_key']}
    network: {node.get('network', 'ws')}
    tls: true
    udp: true
    sni: {node.get('sni') or node['server']}
    client-fingerprint: chrome
    ws-opts:
      path: "{node.get('path', '/')}"
      headers:
        Host: {node.get('host') or node['server']}""")
                public_proxy_names.append(clean_name)

            elif proto == "vmess":
                proxies_yaml.append(f"""  - name: "{clean_name}"
    type: vmess
    server: {node['server']}
    port: {node['port']}
    uuid: {node['uuid_or_key']}
    alterId: 0
    cipher: auto
    network: {node.get('network', 'ws')}
    tls: {str(node.get('security') == 'tls').lower()}
    udp: true
    servername: {node.get('sni') or node['server']}
    ws-opts:
      path: "{node.get('path', '/')}"
      headers:
        Host: {node.get('host') or node['server']}""")
                public_proxy_names.append(clean_name)
    except Exception:
        pass

    all_proxy_options = list(proxy_names) + list(public_proxy_names)

    # Format YAML
    proxies_block = "\n".join(proxies_yaml)
    all_options_yaml = "\n".join([f'      - "{p}"' for p in all_proxy_options])
    public_options_yaml = "\n".join([f'      - "{p}"' for p in (public_proxy_names or proxy_names)])

    yaml_content = f"""# Milijon Clash Meta / Mihomo Config with Live Public Node Harvester
# User: {user['username']} | Generated with Global Healthy Nodes
port: 7890
socks-port: 7891
allow-lan: false
mode: rule
log-level: info
ipv6: false

proxies:
{proxies_block}

proxy-groups:
  - name: "🚀 PROXY"
    type: select
    proxies:
      - "⚡ Auto-Fastest (کم‌ترین پینگ)"
      - "🌐 World Nodes (نودهای جهانی)"
      - "Milijon-VLESS-CleanIP"
      - "Milijon-VLESS-Direct"
      - "Milijon-Trojan-Direct"
      - DIRECT

  - name: "⚡ Auto-Fastest (کم‌ترین پینگ)"
    type: url-test
    url: http://www.gstatic.com/generate_204
    interval: 300
    tolerance: 50
    proxies:
{public_options_yaml}

  - name: "🌐 World Nodes (نودهای جهانی)"
    type: select
    proxies:
{public_options_yaml}

rules:
  - GEOIP,IR,DIRECT
  - GEOIP,CN,DIRECT
  - MATCH,🚀 PROXY
"""
    return yaml_content

def generate_singbox_json(user: Dict[str, Any], domain: str) -> str:
    preset = user.get("country_preset", "iran")
    clean_ip = PRESET_CLEAN_IPS.get(preset, ["104.16.132.229"])[0]

    outbounds: List[Dict[str, Any]] = [
        {
            "type": "vless",
            "tag": "vless-clean-ip",
            "server": clean_ip,
            "server_port": 443,
            "uuid": user["uuid"],
            "tls": {
                "enabled": True,
                "server_name": domain,
                "utls": {"enabled": True, "fingerprint": "chrome"}
            },
            "transport": {
                "type": "ws",
                "path": f"{WS_PATH_VLESS}?ed=2048",
                "headers": {"Host": domain}
            }
        },
        {
            "type": "vless",
            "tag": "vless-direct",
            "server": domain,
            "server_port": 443,
            "uuid": user["uuid"],
            "tls": {
                "enabled": True,
                "server_name": domain,
                "utls": {"enabled": True, "fingerprint": "chrome"}
            },
            "transport": {
                "type": "ws",
                "path": WS_PATH_VLESS,
                "headers": {"Host": domain}
            }
        },
        {
            "type": "trojan",
            "tag": "trojan-direct",
            "server": domain,
            "server_port": 443,
            "password": user["password"],
            "tls": {
                "enabled": True,
                "server_name": domain,
                "utls": {"enabled": True, "fingerprint": "chrome"}
            },
            "transport": {
                "type": "ws",
                "path": WS_PATH_TROJAN,
                "headers": {"Host": domain}
            }
        }
    ]

    base_tags = ["vless-clean-ip", "vless-direct", "trojan-direct"]
    public_tags = []

    # Harvested Public Nodes
    try:
        public_nodes = get_active_public_nodes(limit=25, max_ping=1500)
        for i, node in enumerate(public_nodes):
            tag = f"{node['flag']} {node['country_code']}-{node['protocol'].upper()}-{node['server']} ({node['ping_ms']}ms)"
            proto = node["protocol"].lower()

            if proto == "vless":
                outbounds.append({
                    "type": "vless",
                    "tag": tag,
                    "server": node["server"],
                    "server_port": int(node["port"]),
                    "uuid": node["uuid_or_key"],
                    "tls": {
                        "enabled": node.get("security") == "tls",
                        "server_name": node.get("sni") or node["server"],
                        "utls": {"enabled": True, "fingerprint": "chrome"}
                    },
                    "transport": {
                        "type": node.get("network", "ws"),
                        "path": node.get("path", "/"),
                        "headers": {"Host": node.get("host") or node["server"]}
                    }
                })
                public_tags.append(tag)

            elif proto == "trojan":
                outbounds.append({
                    "type": "trojan",
                    "tag": tag,
                    "server": node["server"],
                    "server_port": int(node["port"]),
                    "password": node["uuid_or_key"],
                    "tls": {
                        "enabled": True,
                        "server_name": node.get("sni") or node["server"],
                        "utls": {"enabled": True, "fingerprint": "chrome"}
                    },
                    "transport": {
                        "type": node.get("network", "ws"),
                        "path": node.get("path", "/"),
                        "headers": {"Host": node.get("host") or node["server"]}
                    }
                })
                public_tags.append(tag)

            elif proto == "vmess":
                outbounds.append({
                    "type": "vmess",
                    "tag": tag,
                    "server": node["server"],
                    "server_port": int(node["port"]),
                    "uuid": node["uuid_or_key"],
                    "security": "auto",
                    "tls": {
                        "enabled": node.get("security") == "tls",
                        "server_name": node.get("sni") or node["server"]
                    },
                    "transport": {
                        "type": node.get("network", "ws"),
                        "path": node.get("path", "/"),
                        "headers": {"Host": node.get("host") or node["server"]}
                    }
                })
                public_tags.append(tag)
    except Exception:
        pass

    selector_outbounds = ["auto-fastest"] + base_tags + public_tags + ["direct"]

    # Assemble sing-box complete config with urltest & selector
    final_outbounds = [
        {
            "type": "selector",
            "tag": "select",
            "outbounds": selector_outbounds
        },
        {
            "type": "urltest",
            "tag": "auto-fastest",
            "outbounds": public_tags or base_tags,
            "url": "http://www.gstatic.com/generate_204",
            "interval": "3m",
            "tolerance": 50
        }
    ] + outbounds + [{"type": "direct", "tag": "direct"}]

    singbox_config = {
        "log": {"level": "info"},
        "inbounds": [
            {"type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": 2080}
        ],
        "outbounds": final_outbounds,
        "route": {
            "rules": [
                {"geoip": ["ir", "cn"], "outbound": "direct"},
                {"outbound": "select"}
            ]
        }
    }
    return json.dumps(singbox_config, indent=2, ensure_ascii=False)
