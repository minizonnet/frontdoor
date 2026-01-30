import os
from dataclasses import dataclass, field

from policy.login_policy import LoginPolicy


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass(frozen=True)
class Settings:
    # OpenStack / portal config
    keystone_url: str = os.environ.get("KEYSTONE_URL", "https://keystone.example.com/v3").rstrip("/")
    user_domain: str = os.environ.get("USER_DOMAIN", "Default")
    horizon_url: str = os.environ.get("HORIZON_URL", "https://opole.minizon.net/")
    skyline_url: str = os.environ.get("SKYLINE_URL", "https://opole.minizon.net:9999/")

    # Branding (can point to your website, or host locally under /static/img)
    brand_name: str = os.environ.get("BRAND_NAME", "MINIZON")
    product_name: str = os.environ.get("PRODUCT_NAME", "Front Door")
    logo_url: str = os.environ.get(
        "LOGO_URL",
        "https://www.minizon.net/wp-content/uploads/2024/04/removal.ai_70e9af3b-2239-4e31-9862-895263aa24ef-minizon-e1713863761615.png",
    )
    bg_img_url: str = os.environ.get(
        "BG_IMG_URL",
        "https://www.minizon.net/wp-content/themes/bizboost/assets/images/promotional-contact.jpg",
    )
    accent_img_url: str = os.environ.get(
        "ACCENT_IMG_URL",
        "https://www.minizon.net/wp-content/uploads/2024/08/cloudstorage-349x349-1.png",
    )
    hero_img_url: str = os.environ.get(
        "HERO_IMG_URL",
        "https://www.minizon.net/wp-content/themes/bizboost/assets/images/hero-content.png",
    )

    # Security / sessions
    session_cookie_secure: bool = _env_bool("SESSION_COOKIE_SECURE", True)

    # Trust X-Forwarded-For from LB/Ingress
    trust_x_forwarded_for: bool = _env_bool("TRUST_X_FORWARDED_FOR", True)

    # Login defense (graduated warnings + captcha) - “global vars” via env
    defense_window_sec: int = int(os.environ.get("DEFENSE_WINDOW_SEC", "900"))
    defense_soft_lockout_sec: int = int(os.environ.get("DEFENSE_SOFT_LOCKOUT_SEC", "300"))

    # Optional: if you still keep these in your defense module; otherwise policy controls it.
    defense_captcha_after_failures: int = int(os.environ.get("DEFENSE_CAPTCHA_AFTER_FAILURES", "4"))
    defense_max_failures_before_block: int = int(os.environ.get("DEFENSE_MAX_FAILURES_BEFORE_BLOCK", "7"))

    # Policy object (centralized thresholds/messages)
    login_policy: LoginPolicy = field(default_factory=LoginPolicy)

