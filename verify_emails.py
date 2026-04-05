#!/usr/bin/env python3
"""
Email verification script.
Reads emails from a CSV file, validates format, MX records, and SMTP mailbox existence.
Writes results to output CSV.

Usage:
    python verify_emails.py input.csv output.csv [--column EMAIL_COLUMN] [--no-smtp]
"""

import csv
import re
import socket
import smtplib
import argparse
import sys
from typing import Optional, Tuple
import dns.resolver  # pip install dnspython

EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)

# Common free/personal email domains (not "professional")
FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "live.com", "msn.com", "me.com", "mac.com",
    "protonmail.com", "proton.me", "zoho.com", "yandex.com",
    "mail.com", "gmx.com", "inbox.com", "fastmail.com",
}


def is_valid_format(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email.strip()))


def get_domain(email: str) -> str:
    return email.strip().split("@")[-1].lower()


def get_mx_hosts(domain: str) -> list:
    try:
        answers = dns.resolver.resolve(domain, "MX")
        return sorted(answers, key=lambda r: r.preference)
    except Exception:
        return []


def has_mx_record(domain: str) -> bool:
    return len(get_mx_hosts(domain)) > 0


def is_professional(domain: str) -> bool:
    return domain not in FREE_EMAIL_DOMAINS


SMTP_RESULTS = {
    "verified": "Mailbox exists (SMTP verified)",
    "unverifiable": "Server blocked SMTP verification (catch-all or greylisting)",
    "invalid": "Mailbox does not exist (SMTP rejected)",
    "error": "SMTP check failed (timeout or connection refused)",
}


def smtp_verify(email: str, mx_hosts: list, timeout: int = 10) -> Tuple[Optional[bool], str]:
    """
    Returns (result, reason):
      True  — mailbox confirmed to exist
      False — mailbox confirmed to NOT exist
      None  — server blocked verification (inconclusive)
    """
    sender = "verify@example.com"

    for mx_record in mx_hosts[:3]:  # try up to 3 MX hosts
        mx_host = str(mx_record.exchange).rstrip(".")
        try:
            with smtplib.SMTP(timeout=timeout) as smtp:
                smtp.connect(mx_host, 25)
                smtp.ehlo_or_helo_if_needed()
                smtp.mail(sender)
                code, _ = smtp.rcpt(email)
                smtp.quit()

                if code == 250:
                    return True, SMTP_RESULTS["verified"]
                elif code in (550, 551, 552, 553, 554):
                    return False, SMTP_RESULTS["invalid"]
                else:
                    # 450, 451, 452 etc — greylisting or temp block
                    return None, SMTP_RESULTS["unverifiable"]

        except smtplib.SMTPRecipientsRefused:
            return False, SMTP_RESULTS["invalid"]
        except smtplib.SMTPServerDisconnected:
            continue  # try next MX
        except (socket.timeout, ConnectionRefusedError, OSError):
            continue  # try next MX

    return None, SMTP_RESULTS["error"]


def verify_email(email: str, do_smtp: bool = True) -> dict:
    email = email.strip()
    result = {
        "email": email,
        "valid_format": False,
        "is_professional": False,
        "has_mx_record": False,
        "smtp_verified": "",
        "status": "",
        "reason": "",
    }

    if not email:
        result["status"] = "INVALID"
        result["reason"] = "Empty email"
        return result

    if not is_valid_format(email):
        result["status"] = "INVALID"
        result["reason"] = "Invalid format"
        return result

    result["valid_format"] = True
    domain = get_domain(email)

    if not is_professional(domain):
        result["is_professional"] = False
        result["status"] = "INVALID"
        result["reason"] = f"Free/personal email domain ({domain})"
        return result

    result["is_professional"] = True

    mx_hosts = get_mx_hosts(domain)
    result["has_mx_record"] = len(mx_hosts) > 0

    if not result["has_mx_record"]:
        result["status"] = "INVALID"
        result["reason"] = f"Domain has no MX record ({domain})"
        return result

    if not do_smtp:
        result["smtp_verified"] = "skipped"
        result["status"] = "VALID"
        result["reason"] = "Passed format, professional domain, and MX check"
        return result

    smtp_result, smtp_reason = smtp_verify(email, mx_hosts)
    result["smtp_verified"] = (
        "yes" if smtp_result is True else
        "no" if smtp_result is False else
        "inconclusive"
    )

    if smtp_result is True:
        result["status"] = "VALID"
        result["reason"] = smtp_reason
    elif smtp_result is False:
        result["status"] = "INVALID"
        result["reason"] = smtp_reason
    else:
        # Inconclusive — domain is valid but server blocked the check
        result["status"] = "LIKELY_VALID"
        result["reason"] = smtp_reason

    return result


def detect_email_column(headers: list, requested: str = None) -> str:
    if requested:
        if requested in headers:
            return requested
        raise ValueError(f"Column '{requested}' not found. Available: {headers}")
    for h in headers:
        if "email" in h.lower():
            return h
    raise ValueError(f"Could not auto-detect email column. Available columns: {headers}")


def run(input_path: str, output_path: str, column: str = None, do_smtp: bool = True):
    results = []

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        email_col = detect_email_column(list(headers), column)

        print(f"Reading from column: '{email_col}'")
        if do_smtp:
            print("SMTP verification enabled (this may take a while)...")
        rows = list(reader)

    total = len(rows)
    print(f"Processing {total} emails...\n")

    for i, row in enumerate(rows, 1):
        email = row.get(email_col, "")
        verification = verify_email(email, do_smtp=do_smtp)
        merged = {**row, **{
            "valid_format": verification["valid_format"],
            "is_professional": verification["is_professional"],
            "has_mx_record": verification["has_mx_record"],
            "smtp_verified": verification["smtp_verified"],
            "verification_status": verification["status"],
            "verification_reason": verification["reason"],
        }}
        results.append(merged)

        icon = "✓" if verification["status"] == "VALID" else ("~" if verification["status"] == "LIKELY_VALID" else "✗")
        print(f"  [{i}/{total}] {icon} {email or '(empty)'} — {verification['reason']}")

    out_fields = list(rows[0].keys()) + [
        "valid_format", "is_professional", "has_mx_record", "smtp_verified",
        "verification_status", "verification_reason"
    ] if rows else []

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(results)

    valid = sum(1 for r in results if r["verification_status"] == "VALID")
    likely = sum(1 for r in results if r["verification_status"] == "LIKELY_VALID")
    invalid = sum(1 for r in results if r["verification_status"] == "INVALID")
    print(f"\nDone. {total} emails processed:")
    print(f"  ✓ VALID:        {valid}")
    print(f"  ~ LIKELY_VALID: {likely}  (server blocked SMTP check)")
    print(f"  ✗ INVALID:      {invalid}")
    print(f"\nResults saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Verify professional emails from a CSV file.")
    parser.add_argument("input", help="Path to input CSV file")
    parser.add_argument("output", help="Path to output CSV file")
    parser.add_argument("--column", "-c", default=None,
                        help="Name of the email column (auto-detected if not provided)")
    parser.add_argument("--no-smtp", action="store_true",
                        help="Skip SMTP verification (faster, less accurate)")
    args = parser.parse_args()

    try:
        run(args.input, args.output, args.column, do_smtp=not args.no_smtp)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
