from dataclasses import dataclass

@dataclass(frozen=True)
class LoginPolicy:
    # Thresholds (by number of failed attempts within the defense window)
    warn_until_failures: int = 3          # show "X tries left" for failures 1..3
    captcha_warn_failure: int = 4         # after 4th failure: "captcha next"
    captcha_start_failure: int = 5        # captcha required starting at 5th attempt
    block_warn_from_failure: int = 5      # start red warning here
    block_after_failure: int = 7          # would block at 7th failure (simulate lockout)

    # Copy you want for UI
    msg_invalid_generic: str = "Invalid credentials."
    msg_captcha_next: str = "Invalid credentials. Next attempt will require a captcha."
    msg_captcha_required: str = "Captcha is now required."
    msg_would_block: str = "Too many incorrect attempts. Your IP would be blocked now (blocking module later)."
    msg_block_countdown: str = "{n} more incorrect attempt(s) and your IP will be blocked."

