import yaml
import os

_config = None

def load_config():
    global _config
    if _config is not None:
        return _config
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    
    with open(config_path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)
    
    return _config

def get_redis_config():
    cfg = load_config()
    redis_cfg = cfg.get("redis", {})
    return {
        "host": redis_cfg.get("host", "127.0.0.1"),
        "port": redis_cfg.get("port", 6379),
        "db": redis_cfg.get("db", 0),
        "password": redis_cfg.get("password", "") or None,
    }

def get_server_config():
    cfg = load_config()
    server_cfg = cfg.get("server", {})
    return {
        "host": server_cfg.get("host", "0.0.0.0"),
        "port": server_cfg.get("port", 8000),
    }

def get_gpu_config():
    cfg = load_config()
    gpu_cfg = cfg.get("gpu", {})
    return {
        "check_interval": gpu_cfg.get("check_interval", 5),
        "safety_margin": gpu_cfg.get("safety_margin", 0.5),
    }
