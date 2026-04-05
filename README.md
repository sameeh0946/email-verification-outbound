# 📧 Email Verification Tool
> A self-hosted replacement for ZeroBounce — verify professional emails from a CSV file using Python.

A simple Python tool that checks whether a list of professional email addresses are valid — before you send anything.

---

## What does it do?

You give it a CSV file full of email addresses. It checks each one and tells you:

| Check | What it means |
|---|---|
| ✅ Valid format | The email looks like a real email (`name@company.com`) |
| ✅ Professional domain | It's not a free/personal email like Gmail or Yahoo |
| ✅ MX record exists | The company's mail server is actually reachable |
| ✅ SMTP check | Tries to confirm the specific inbox exists (when servers allow it) |

At the end, every email gets one of three statuses:

- **VALID** — confirmed good ✓
- **LIKELY_VALID** — looks good, but the mail server blocked our inbox probe (very common for corporate emails)
- **INVALID** — bad format, free email, or domain doesn't exist ✗

---

## How to use it

### 1. Install the one dependency

```bash
pip install dnspython
```

### 2. Prepare your CSV

Your CSV just needs a column with email addresses. The column can be named anything containing the word "email" (e.g. `email`, `work_email`, `contact_email`).

Example `contacts.csv`:
```
name,email,company
Alice,alice@stripe.com,Stripe
Bob,bob@gmail.com,Freelance
```

### 3. Run the script

```bash
python verify_emails.py contacts.csv results.csv
```

If your email column has a custom name:

```bash
python verify_emails.py contacts.csv results.csv --column contact_professions_email
```

To skip SMTP check (faster, slightly less accurate):

```bash
python verify_emails.py contacts.csv results.csv --no-smtp
```

### 4. Check your results

The output CSV will have all your original columns plus these new ones:

| Column | Description |
|---|---|
| `valid_format` | True/False |
| `is_professional` | True/False — not Gmail/Yahoo/etc. |
| `has_mx_record` | True/False — domain has a mail server |
| `smtp_verified` | `yes` / `no` / `inconclusive` / `skipped` |
| `verification_status` | `VALID`, `LIKELY_VALID`, or `INVALID` |
| `verification_reason` | Plain English explanation |

---

## Example output

```
Processing 111 emails...

  [1/111] ✓ alice@stripe.com — Mailbox exists (SMTP verified)
  [2/111] ~ bob@company.com — Server blocked SMTP verification (catch-all or greylisting)
  [3/111] ✗ fake@nonexistent.xyz — Domain has no MX record

Done. 111 emails processed:
  ✓ VALID:        5
  ~ LIKELY_VALID: 104  (server blocked SMTP check)
  ✗ INVALID:      2
```

---

## Why does "LIKELY_VALID" happen so often?

Most corporate mail servers (Microsoft 365, Google Workspace, etc.) **intentionally block** tools from probing whether a specific inbox exists — this is a spam prevention measure. So getting `LIKELY_VALID` is completely normal and means the domain and format are fine, but we just can't confirm the exact inbox without actually sending an email.

---

## Files

| File | Description |
|---|---|
| `verify_emails.py` | Main script |
| `README.md` | This file |

---

## Requirements

- Python 3.7+
- [`dnspython`](https://www.dnspython.org/) — `pip install dnspython`
