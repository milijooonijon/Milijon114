import os
import secrets

# Server & Network Configuration
PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")

# Security & Credentials
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "milijon_admin")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(16))

# Domain & Paths
SERVER_DOMAIN = os.getenv("SERVER_DOMAIN", "")  # Auto-detected from Host header if empty
WS_PATH_VLESS = os.getenv("WS_PATH_VLESS", "/milijon-vl")
WS_PATH_TROJAN = os.getenv("WS_PATH_TROJAN", "/milijon-tr")
DB_PATH = os.getenv("DB_PATH", "milijon.db")

# Default CDN / Clean IPs for Circumvention Presets
PRESET_CLEAN_IPS = {
    "iran": [
        "104.16.132.229",
        "104.16.133.229",
        "172.67.181.18",
        "104.17.147.22",
        "162.159.140.97",
        "141.101.90.10"
    ],
    "china": [
        "104.18.2.161",
        "104.19.18.151",
        "172.64.80.1",
        "198.41.214.162"
    ],
    "russia": [
        "104.21.35.12",
        "172.67.143.205",
        "188.114.96.3",
        "188.114.97.3"
    ]
}

# Regional Fragmentation Presets for bypassing DPI
PRESET_FRAGMENT = {
    "iran": {"length": "100-200", "interval": "10-20", "packets": "tlshello"},
    "china": {"length": "50-100", "interval": "5-15", "packets": "1-3"},
    "russia": {"length": "100-300", "interval": "10-30", "packets": "tlshello"}
}

# Public Node Harvester & Health Check Configuration
HARVESTER_ENABLED = os.getenv("HARVESTER_ENABLED", "true").lower() in ("true", "1", "yes")
HARVESTER_INTERVAL_MINUTES = int(os.getenv("HARVESTER_INTERVAL_MINUTES", "30"))
HARVESTER_MAX_NODES = int(os.getenv("HARVESTER_MAX_NODES", "60"))
HARVESTER_MAX_PING = int(os.getenv("HARVESTER_MAX_PING", "1500"))
HARVESTER_TIMEOUT_SEC = float(os.getenv("HARVESTER_TIMEOUT_SEC", "2.0"))

# Reputable Public GitHub Sources for Free Global Nodes
HARVESTER_SOURCES = [
    "https://raw.githubusercontent.com/yebekhe/TVC/main/subscriptions/xray/normal/mix",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/Sub1.txt",
    "https://raw.githubusercontent.com/LonUp/NodeList/main/v2ray/v2ray.txt",
    "https://raw.githubusercontent.com/freefq/free/master/v2"
]
