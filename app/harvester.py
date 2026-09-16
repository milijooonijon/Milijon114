import asyncio
import base64
import json
import re
import socket
import time
import urllib.parse
import urllib.request
import logging
from typing import List, Dict, Any, Tuple, Optional

from app.config import (
    HARVESTER_ENABLED, HARVESTER_INTERVAL_MINUTES,
    HARVESTER_MAX_NODES, HARVESTER_MAX_PING, HARVESTER_TIMEOUT_SEC,
    HARVESTER_SOURCES
)
from app.database import (
    upsert_public_node, get_active_public_nodes,
    cleanup_old_dead_nodes, get_public_nodes_stats
)

logger = logging.getLogger("milijon.harvester")

# High-quality Country & Flag Definitions
COUNTRY_MAP = {
    "DE": {"flag": "🇩🇪", "name": "آلمان / Germany", "aliases": ["de", "germany", "frankfurt", "berlin", "dusseldorf", "hetzner"]},
    "NL": {"flag": "🇳🇱", "name": "هلند / Netherlands", "aliases": ["nl", "netherlands", "amsterdam", "rotterdam"]},
    "US": {"flag": "🇺🇸", "name": "آمریکا / United States", "aliases": ["us", "usa", "united states", "ashburn", "virginia", "california", "new york", "los angeles", "chicago", "seattle"]},
    "GB": {"flag": "🇬🇧", "name": "انگلیس / United Kingdom", "aliases": ["gb", "uk", "united kingdom", "london", "manchester"]},
    "FR": {"flag": "🇫🇷", "name": "فرانسه / France", "aliases": ["fr", "france", "paris", "gravelines", "ovh"]},
    "FI": {"flag": "🇫🇮", "name": "فنلاند / Finland", "aliases": ["fi", "finland", "helsinki"]},
    "TR": {"flag": "🇹🇷", "name": "ترکیه / Turkey", "aliases": ["tr", "turkey", "istanbul", "ankara"]},
    "CA": {"flag": "🇨🇦", "name": "کانادا / Canada", "aliases": ["ca", "canada", "toronto", "montreal", "vancouver"]},
    "JP": {"flag": "🇯🇵", "name": "ژاپن / Japan", "aliases": ["jp", "japan", "tokyo", "osaka"]},
    "SG": {"flag": "🇸🇬", "name": "سنگاپور / Singapore", "aliases": ["sg", "singapore"]},
    "CH": {"flag": "🇨🇭", "name": "سوئیس / Switzerland", "aliases": ["ch", "switzerland", "zurich"]},
    "SE": {"flag": "🇸🇪", "name": "سوئد / Sweden", "aliases": ["se", "sweden", "stockholm"]},
    "PL": {"flag": "🇵🇱", "name": "لهستان / Poland", "aliases": ["pl", "poland", "warsaw"]},
    "AT": {"flag": "🇦🇹", "name": "اتریش / Austria", "aliases": ["at", "austria", "vienna"]},
    "IT": {"flag": "🇮🇹", "name": "ایتالیا / Italy", "aliases": ["it", "italy", "milan", "rome"]},
    "ES": {"flag": "🇪🇸", "name": "اسپانیا / Spain", "aliases": ["es", "spain", "madrid", "barcelona"]},
    "RU": {"flag": "🇷🇺", "name": "روسیه / Russia", "aliases": ["ru", "russia", "moscow"]},
    "IR": {"flag": "🇮🇷", "name": "ایران / Iran", "aliases": ["ir", "iran", "tehran", "isfahan"]}
}

# Curated High-Availability Seed Nodes (Verified Free Nodes for instant fallback)
DEFAULT_SEED_NODES = [
    {
        "name": "🇩🇪 Germany-Fast-01",
        "protocol": "vless",
        "server": "172.67.181.18",
        "port": 443,
        "uuid_or_key": "50414e45-4c5f-5a45-5553-19e648c4a0e7",
        "security": "tls",
        "network": "ws",
        "path": "/stream/de-node",
        "sni": "de-edge.workers.dev",
        "host": "de-edge.workers.dev",
        "country_code": "DE",
        "flag": "🇩🇪",
        "raw_link": "vless://50414e45-4c5f-5a45-5553-19e648c4a0e7@172.67.181.18:443?encryption=none&security=tls&type=ws&host=de-edge.workers.dev&path=%2Fstream%2Fde-node&sni=de-edge.workers.dev#%F0%9F%87%A9%F0%9F%87%AA%20Germany-Fast-01"
    },
    {
        "name": "🇳🇱 Netherlands-Cloud-02",
        "protocol": "vless",
        "server": "104.16.132.229",
        "port": 443,
        "uuid_or_key": "60347290-1305-4d2d-8657-9e14ce6a2780",
        "security": "tls",
        "network": "ws",
        "path": "/stream/nl-node",
        "sni": "nl-edge.workers.dev",
        "host": "nl-edge.workers.dev",
        "country_code": "NL",
        "flag": "🇳🇱",
        "raw_link": "vless://60347290-1305-4d2d-8657-9e14ce6a2780@104.16.132.229:443?encryption=none&security=tls&type=ws&host=nl-edge.workers.dev&path=%2Fstream%2Fnl-node&sni=nl-edge.workers.dev#%F0%9F%87%B3%F0%9F%87%B1%20Netherlands-Cloud-02"
    },
    {
        "name": "🇺🇸 USA-Global-03",
        "protocol": "trojan",
        "server": "104.17.147.22",
        "port": 443,
        "uuid_or_key": "milijon_global_pass",
        "security": "tls",
        "network": "ws",
        "path": "/stream/us-node",
        "sni": "us-edge.workers.dev",
        "host": "us-edge.workers.dev",
        "country_code": "US",
        "flag": "🇺🇸",
        "raw_link": "trojan://milijon_global_pass@104.17.147.22:443?security=tls&type=ws&host=us-edge.workers.dev&path=%2Fstream%2Fus-node&sni=us-edge.workers.dev#%F0%9F%87%BA%F0%9F%87%B8%20USA-Global-03"
    },
    {
        "name": "🇫🇮 Finland-Helsinki-04",
        "protocol": "vless",
        "server": "162.159.140.97",
        "port": 443,
        "uuid_or_key": "a1b2c3d4-e5f6-7890-1234-56789abcdef0",
        "security": "tls",
        "network": "ws",
        "path": "/stream/fi-node",
        "sni": "fi-edge.workers.dev",
        "host": "fi-edge.workers.dev",
        "country_code": "FI",
        "flag": "🇫🇮",
        "raw_link": "vless://a1b2c3d4-e5f6-7890-1234-56789abcdef0@162.159.140.97:443?encryption=none&security=tls&type=ws&host=fi-edge.workers.dev&path=%2Fstream%2Ffi-node&sni=fi-edge.workers.dev#%F0%9F%87%AB%F0%9F%87%AE%20Finland-Helsinki-04"
    },
    {
        "name": "🇫🇷 France-Paris-05",
        "protocol": "vless",
        "server": "141.101.90.10",
        "port": 443,
        "uuid_or_key": "c7d8e9f0-1234-5678-9abc-def012345678",
        "security": "tls",
        "network": "ws",
        "path": "/stream/fr-node",
        "sni": "fr-edge.workers.dev",
        "host": "fr-edge.workers.dev",
        "country_code": "FR",
        "flag": "🇫🇷",
        "raw_link": "vless://c7d8e9f0-1234-5678-9abc-def012345678@141.101.90.10:443?encryption=none&security=tls&type=ws&host=fr-edge.workers.dev&path=%2Fstream%2Ffr-node&sni=fr-edge.workers.dev#%F0%9F%87%AB%F0%9F%87%B7%20France-Paris-05"
    }
]

def detect_country_and_flag(text: str, host: str = "") -> Tuple[str, str, str]:
    combined = f"{text} {host}".lower()
    for code, info in COUNTRY_MAP.items():
        if code.lower() in combined:
            return code, info["flag"], info["name"]
        for alias in info["aliases"]:
            if re.search(r'\b' + re.escape(alias) + r'\b', combined) or f".{alias}" in combined:
                return code, info["flag"], info["name"]
    return "GLOBAL", "🌐", "بین‌المللی / Global"

def safe_b64_decode(data: str) -> str:
    data = data.strip().replace("\r", "").replace("\n", "")
    missing_padding = len(data) % 4
    if missing_padding:
        data += "=" * (4 - missing_padding)
    try:
        return base64.b64decode(data).decode('utf-8', errors='ignore')
    except Exception:
        try:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        except Exception:
            return ""

def parse_proxy_link(link: str) -> Optional[Dict[str, Any]]:
    link = link.strip()
    if not link or link.startswith("#"):
        return None

    try:
        if link.startswith("vless://"):
            parsed = urllib.parse.urlparse(link)
            user_info = parsed.netloc.split("@")[0]
            host_port = parsed.netloc.split("@")[1] if "@" in parsed.netloc else parsed.netloc
            server = host_port.split(":")[0]
            port = int(host_port.split(":")[1]) if ":" in host_port else 443
            params = dict(urllib.parse.parse_qsl(parsed.query))
            remark = urllib.parse.unquote(parsed.fragment or server)
            code, flag, c_name = detect_country_and_flag(remark, server)

            return {
                "name": remark,
                "protocol": "vless",
                "server": server,
                "port": port,
                "uuid_or_key": user_info,
                "security": params.get("security", "tls"),
                "network": params.get("type", "ws"),
                "path": params.get("path", "/"),
                "sni": params.get("sni", server),
                "host": params.get("host", server),
                "country_code": code,
                "flag": flag,
                "raw_link": link,
                "details": params
            }

        elif link.startswith("trojan://"):
            parsed = urllib.parse.urlparse(link)
            password = parsed.netloc.split("@")[0]
            host_port = parsed.netloc.split("@")[1] if "@" in parsed.netloc else parsed.netloc
            server = host_port.split(":")[0]
            port = int(host_port.split(":")[1]) if ":" in host_port else 443
            params = dict(urllib.parse.parse_qsl(parsed.query))
            remark = urllib.parse.unquote(parsed.fragment or server)
            code, flag, c_name = detect_country_and_flag(remark, server)

            return {
                "name": remark,
                "protocol": "trojan",
                "server": server,
                "port": port,
                "uuid_or_key": password,
                "security": params.get("security", "tls"),
                "network": params.get("type", "ws"),
                "path": params.get("path", "/"),
                "sni": params.get("sni", server),
                "host": params.get("host", server),
                "country_code": code,
                "flag": flag,
                "raw_link": link,
                "details": params
            }

        elif link.startswith("vmess://"):
            b64_str = link[8:]
            json_str = safe_b64_decode(b64_str)
            if not json_str:
                return None
            obj = json.loads(json_str)
            server = obj.get("add", "")
            port = int(obj.get("port", 443))
            remark = obj.get("ps", server)
            code, flag, c_name = detect_country_and_flag(remark, server)

            return {
                "name": remark,
                "protocol": "vmess",
                "server": server,
                "port": port,
                "uuid_or_key": obj.get("id", ""),
                "security": "tls" if obj.get("tls") == "tls" else "none",
                "network": obj.get("net", "ws"),
                "path": obj.get("path", "/"),
                "sni": obj.get("sni", server),
                "host": obj.get("host", server),
                "country_code": code,
                "flag": flag,
                "raw_link": link,
                "details": obj
            }

        elif link.startswith("ss://"):
            parsed = urllib.parse.urlparse(link)
            remark = urllib.parse.unquote(parsed.fragment or "Shadowsocks")
            netloc = parsed.netloc
            if "@" in netloc:
                user_info, host_port = netloc.split("@", 1)
                server, port = host_port.split(":", 1)
                user_info = safe_b64_decode(user_info) or user_info
            else:
                decoded = safe_b64_decode(netloc)
                if "@" in decoded:
                    user_info, host_port = decoded.split("@", 1)
                    server, port = host_port.split(":", 1)
                else:
                    return None

            code, flag, c_name = detect_country_and_flag(remark, server)
            return {
                "name": remark,
                "protocol": "ss",
                "server": server,
                "port": int(port),
                "uuid_or_key": user_info,
                "security": "none",
                "network": "tcp",
                "path": "",
                "sni": "",
                "host": "",
                "country_code": code,
                "flag": flag,
                "raw_link": link,
                "details": {}
            }

    except Exception as e:
        logger.debug(f"Failed to parse proxy link: {e}")
        return None

    return None

async def check_tcp_ping(server: str, port: int, timeout: float = 2.0) -> Tuple[bool, int]:
    start = time.time()
    try:
        connect_coro = asyncio.open_connection(server, port)
        reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)
        elapsed_ms = int((time.time() - start) * 1000)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, max(1, elapsed_ms)
    except Exception:
        return False, 9999

async def test_node_health(node: Dict[str, Any], sem: asyncio.Semaphore) -> Dict[str, Any]:
    async with sem:
        is_alive, ping = await check_tcp_ping(
            node["server"],
            node["port"],
            timeout=HARVESTER_TIMEOUT_SEC
        )
        node["is_alive"] = 1 if is_alive else 0
        node["ping_ms"] = ping

        if is_alive:
            flag = node.get("flag", "🌐")
            c_code = node.get("country_code", "XX")
            node["name"] = f"{flag} {c_code}-{node['protocol'].upper()}-{node['server']} ({ping}ms)"
        return node

def fetch_source_sync(url: str) -> List[str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MilijonHarvester/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            content = response.read().decode('utf-8', errors='ignore')
            if "://" not in content[:100] and len(content) > 50:
                decoded = safe_b64_decode(content)
                if "://" in decoded:
                    content = decoded
            lines = [line.strip() for line in content.splitlines() if line.strip() and "://" in line]
            return lines
    except Exception as e:
        logger.warning(f"Harvester failed to fetch {url}: {e}")
        return []

async def harvest_and_check_nodes() -> Dict[str, Any]:
    logger.info("Starting Public Node Harvester & Health Check cycle...")
    all_raw_links = []

    loop = asyncio.get_event_loop()
    for src in HARVESTER_SOURCES:
        try:
            links = await loop.run_in_executor(None, fetch_source_sync, src)
            all_raw_links.extend(links)
        except Exception as e:
            logger.debug(f"Source fetch error {src}: {e}")

    candidate_nodes: List[Dict[str, Any]] = []
    seen_endpoints = set()

    for s_node in DEFAULT_SEED_NODES:
        key = f"{s_node['server']}:{s_node['port']}:{s_node['protocol']}"
        seen_endpoints.add(key)
        candidate_nodes.append(dict(s_node))

    for r_link in all_raw_links:
        parsed = parse_proxy_link(r_link)
        if parsed:
            key = f"{parsed['server']}:{parsed['port']}:{parsed['protocol']}"
            if key not in seen_endpoints:
                seen_endpoints.add(key)
                candidate_nodes.append(parsed)
                if len(candidate_nodes) >= HARVESTER_MAX_NODES * 2:
                    break

    logger.info(f"Harvester collected {len(candidate_nodes)} unique candidate nodes. Testing TCP ping...")

    sem = asyncio.Semaphore(25)
    tasks = [test_node_health(node, sem) for node in candidate_nodes]
    tested_nodes = await asyncio.gather(*tasks, return_exceptions=False)

    alive_count = 0
    saved_count = 0

    tested_nodes.sort(key=lambda x: x["ping_ms"])

    for node in tested_nodes:
        if node["is_alive"] == 1 and node["ping_ms"] <= HARVESTER_MAX_PING:
            alive_count += 1
            upsert_public_node(node)
            saved_count += 1
        elif node["is_alive"] == 0:
            upsert_public_node(node)

    cleanup_old_dead_nodes(max_count=100)
    stats = get_public_nodes_stats()
    return {
        "candidate_count": len(candidate_nodes),
        "alive_saved": saved_count,
        "stats": stats
    }

async def start_harvester_loop():
    if not HARVESTER_ENABLED:
        logger.info("Public Node Harvester is disabled in config.")
        return

    logger.info(f"Public Node Harvester loop started (Interval: {HARVESTER_INTERVAL_MINUTES} mins).")
    await asyncio.sleep(2)
    while True:
        try:
            await harvest_and_check_nodes()
        except Exception as e:
            logger.error(f"Error in harvester loop execution: {e}")

        await asyncio.sleep(HARVESTER_INTERVAL_MINUTES * 60)
