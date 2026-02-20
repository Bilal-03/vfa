"""
modules.py — Consolidated Finance Bot Module
Contains: EMI Calculator, FD Calculator, SIP Calculator
All phrase triggers are embedded directly (no external .txt files needed).
"""

import re


# ---------------------------------------------------------------------------
# Embedded Trigger Phrases
# ---------------------------------------------------------------------------

EMI_PHRASES = [
    "tell me the emi", "tell me my emi", "tell the emi", "EMI for", "emi for",
    "calculate my emi", "calculate the emi", "calculate emi", "emi calculation",
    "give me the emi", "calculate my loan", "calculate monthly payment",
    "calculate loan installment", "loan emi", "what will be my emi",
    "Can you help me calculate my EMI?", "What's the monthly payment on my loan?",
    "How much do I need to pay monthly for my loan?",
    "Can you tell me the installment amount for my loan?",
    "What's the EMI for my loan?",
    "Could you calculate the monthly loan payment for me?",
    "I need to know my loan EMI, can you assist?",
    "What's the monthly installment for my loan?",
    "Can you provide the EMI calculation for my loan?",
    "Tell me the EMI amount for my loan.",
    "How do I calculate my loan EMI?",
    "What's my monthly loan repayment amount?",
    "Can you help me with the EMI calculation?",
    "What's the loan installment amount I should pay each month?",
    "How much do I have to pay monthly on my loan?",
    "What's the monthly payment for my loan?",
    "Please calculate the EMI for my loan.",
    "How do I determine my loan EMI?",
    "Tell me my loan's monthly payment.",
    "What's the installment amount I owe each month?",
    "Can you calculate my loan's monthly installment?",
    "I need to know my monthly loan repayment, can you help?",
    "Please provide the EMI details for my loan.",
    "How do I find out my loan's EMI?",
    "Could you assist me with my loan's EMI calculation?",
    "What's the monthly payment I need to make towards my loan?",
    "Can you tell me the EMI amount for my loan term?",
    "How can I calculate the monthly payment for my loan?",
    "Please help me determine my loan EMI.",
]

FD_PHRASES = [
    "Calculate my FD maturity.", "Calculate my FD", "Calculate FD",
    "Calculate Fixed Deposit", "calculate the fixed deposit",
    "calculate my fixed deposit return", "calculate my fixed deposit",
    "calculate returns on fd", "tell me the fixed deposit",
    "Calculate my fixed deposit interest.",
    "What's the maturity value of my fixed deposit?",
    "Determine the interest on my fixed deposit",
    "Calculate the interest earned on my fixed deposit.",
    "Can you help me with my FD calculation?",
    "Determine the maturity value of my FD investment.",
    "Calculate the interest for my fixed deposit.",
    "How much will my FD earn?",
    "Tell me the maturity amount for my fixed deposit.",
    "Calculate the returns on my FD.",
    "What will be the maturity value of my FD?",
    "Please calculate the interest for my fixed deposit term.",
    "How do I calculate the returns on my FD?",
    "Determine the interest earned on my fixed deposit investment.",
    "Calculate the growth of my fixed deposit.",
    "What's the interest rate for my FD?",
    "Calculate the total interest on my fixed deposit.",
    "Can you determine the interest earned on my FD?",
    "Tell me the interest rate for my fixed deposit.",
    "How much interest will my FD accrue?",
    "Calculate the interest payout for my fixed deposit.",
    "Determine the growth of my FD investment.",
    "What will be the interest payout for my FD?",
    "Please calculate the interest earned on my fixed deposit investment.",
    "How do I calculate the interest on my fixed deposit?",
    "Calculate the maturity value of my FD investment.",
    "Can you help me with the calculation of my fixed deposit interest?",
    "Determine the total interest earned on my fixed deposit.",
    "Calculate the interest compounded on my FD.",
]


# ---------------------------------------------------------------------------
# EMI Calculator Bot
# ---------------------------------------------------------------------------

class Chatterbot:
    """EMI / Loan calculator bot."""

    def respond(self, input_text):
        if any(phrase.lower() in input_text.lower() for phrase in EMI_PHRASES):
            principal, rate, years = self._extract_loan_details(input_text)
            if principal is not None and rate is not None and years is not None:
                monthly, total, interest = self._calculate_emi(principal, rate, years)
                return (
                    f"Your monthly EMI will be ₹{monthly:.2f}. "
                    f"Total Payment: ₹{total:.2f}, "
                    f"Total Interest: ₹{interest:.2f}"
                )
            return "I'm sorry, I couldn't extract the necessary details from your input."
        if "exit" in input_text.lower():
            return "Goodbye!"
        return "I'm sorry, I don't understand that."

    # ------------------------------------------------------------------
    def _calculate_emi(self, principal, annual_rate, years):
        monthly_rate = annual_rate / 12 / 100
        months = years * 12
        monthly = (principal * monthly_rate) / (1 - (1 + monthly_rate) ** -months)
        total = monthly * months
        interest = total - principal
        return monthly, total, interest

    def _extract_loan_details(self, text):
        principal = annual_rate = years = None

        def parse_amount(raw_num, suffix=''):
            try:
                val = float(raw_num.replace(',', ''))
            except Exception:
                return None
            s = (suffix or '').lower().strip()
            if s in ('l', 'lac', 'lakh', 'lakhs', 'lacs'):
                val *= 100_000
            elif s == 'k':
                val *= 1_000
            elif s in ('cr', 'crore', 'crores'):
                val *= 10_000_000
            return val

        # Pattern 1: ₹1L / ₹1 lakh / ₹5,00,000
        m = re.search(
            r'(?:₹\s*|rs\.?\s*|inr\s*)(\d+(?:[,\d]*)?(?:\.\d+)?)\s*(l|lac|lakh|lakhs|lacs|k|cr|crore|crores)?',
            text, re.IGNORECASE)
        if m:
            principal = parse_amount(m.group(1), m.group(2) or '')

        # Pattern 2: 1L / 1 lakh / 5cr (no prefix)
        if principal is None:
            m = re.search(
                r'\b(\d+(?:\.\d+)?)\s*(l|lac|lakh|lakhs|lacs|k|cr|crore|crores)\b',
                text, re.IGNORECASE)
            if m:
                principal = parse_amount(m.group(1), m.group(2))

        # Pattern 3: plain number followed by rs/rupee suffix
        if principal is None:
            m = re.search(
                r'(\d+(?:[,\d]*)?(?:\.\d+)?)\s*(?:rs\.?|rupee|rupees|inr)\b',
                text, re.IGNORECASE)
            if m:
                principal = parse_amount(m.group(1))

        # Interest rate
        m = re.search(r"(\d+(?:\.\d+)?)(?:%|\s*%|\s*percent)", text, re.IGNORECASE)
        if m:
            annual_rate = float(m.group(1))

        # Tenure — numeric years
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", text, re.IGNORECASE)
        if m:
            years = float(m.group(1))

        # Tenure — word form
        if not years:
            word_map = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
                "fifteen": 15, "sixteen": 16, "seventeen": 17,
                "eighteen": 18, "nineteen": 19, "twenty": 20,
            }
            m = re.search(
                r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)"
                r"\s*(?:years?|yrs?)",
                text, re.IGNORECASE
            )
            if m:
                years = word_map.get(m.group(1).lower())

        return principal, annual_rate, years


# ---------------------------------------------------------------------------
# FD Calculator Bot
# ---------------------------------------------------------------------------

class FDCalculatorBot:
    """Fixed Deposit calculator bot."""

    def respond(self, input_text):
        if any(phrase.lower() in input_text.lower() for phrase in FD_PHRASES):
            principal, rate, days, monthly_payout = self._extract_fd_details(input_text)
            if principal is not None and rate is not None and days is not None:
                maturity = self._calculate_maturity(principal, rate, days, monthly_payout)
                return f"The maturity amount for the Fixed Deposit is ₹{maturity:.2f}"
            return "I'm sorry, I couldn't extract the necessary details from your input."
        if "exit" in input_text.lower():
            return "Goodbye!"
        return "I'm sorry, I don't understand that."

    # ------------------------------------------------------------------
    def _calculate_maturity(self, principal, annual_rate, days, monthly_payout=False):
        rate = annual_rate / 100
        years = days / 365
        if years <= 0.5:
            maturity = principal * (1 + rate * years)
        else:
            if monthly_payout:
                total_interest = principal * rate * years
                maturity = principal + total_interest
            else:
                maturity = principal * (1 + rate) ** years
        return round(maturity, 2)

    def _extract_fd_details(self, text):
        principal = rate = days = None
        monthly_payout = False

        def parse_amount(raw_num, suffix=''):
            try:
                val = float(raw_num.replace(',', ''))
            except Exception:
                return None
            s = (suffix or '').lower().strip()
            if s in ('l', 'lac', 'lakh', 'lakhs', 'lacs'):
                val *= 100_000
            elif s == 'k':
                val *= 1_000
            elif s in ('cr', 'crore', 'crores'):
                val *= 10_000_000
            return val

        # Pattern 1: ₹1L / ₹1 lakh / ₹1,00,000
        m = re.search(
            r'(?:₹\s*|rs\.?\s*|inr\s*)(\d+(?:[,\d]*)?(?:\.\d+)?)\s*(l|lac|lakh|lakhs|lacs|k|cr|crore|crores)?',
            text, re.IGNORECASE)
        if m:
            principal = parse_amount(m.group(1), m.group(2) or '')

        # Pattern 2: 1L / 1 lakh (no prefix)
        if principal is None:
            m = re.search(
                r'\b(\d+(?:\.\d+)?)\s*(l|lac|lakh|lakhs|lacs|k|cr|crore|crores)\b',
                text, re.IGNORECASE)
            if m:
                principal = parse_amount(m.group(1), m.group(2))

        # Pattern 3: plain number followed by rs/rupee suffix
        if principal is None:
            m = re.search(
                r'(\d+(?:[,\d]*)?(?:\.\d+)?)\s*(?:rs\.?|rupee|rupees|inr)\b',
                text, re.IGNORECASE)
            if m:
                principal = parse_amount(m.group(1))

        # Pattern 4: plain large number fallback (≥4 digits)
        if principal is None:
            m = re.search(r'\b(\d{4,}(?:[,\d]*)?)\b', text)
            if m:
                principal = parse_amount(m.group(1))

        # Interest rate
        m = re.search(r"(\d+(?:\.\d+)?)(?:%|\s*%|\s*percent)", text, re.IGNORECASE)
        if m:
            rate = float(m.group(1))

        # Duration — numeric (days / months / years)
        m = re.search(
            r"(\d+(?:\.\d+)?)\s*(day|days|da|month|months|mon|year|years|yea)",
            text, re.IGNORECASE
        )
        if m:
            days = self._to_days(m.group(1), m.group(2))

        # Duration — word form
        if not days:
            word_map = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
                "fifteen": 15, "sixteen": 16, "seventeen": 17,
                "eighteen": 18, "nineteen": 19, "twenty": 20,
            }
            m = re.search(
                r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)"
                r"\s*(day|days|da|month|months|mon|year|years|yea)",
                text, re.IGNORECASE
            )
            if m:
                num = word_map.get(m.group(1).lower(), 1)
                days = self._to_days(str(num), m.group(2))

        if re.search(r"monthly interest payout", text, re.IGNORECASE):
            monthly_payout = True

        return principal, rate, days, monthly_payout

    @staticmethod
    def _to_days(amount_str, unit):
        amount = float(amount_str)
        unit = unit.lower()
        if unit in ("day", "days", "da"):
            return amount
        if unit in ("month", "months", "mon"):
            return amount * 30
        if unit in ("year", "years", "yea"):
            return amount * 365
        raise ValueError(f"Unknown duration unit: {unit}")


# ---------------------------------------------------------------------------
# SIP Calculator Bot
# ---------------------------------------------------------------------------

class SipChatterbot:
    """Systematic Investment Plan (SIP) calculator bot."""

    _KEYWORDS = ["sip", "systematic investment", "monthly investment"]

    def respond(self, input_text):
        if any(kw in input_text.lower() for kw in self._KEYWORDS):
            return self._extract_and_calculate(input_text)
        if "exit" in input_text.lower():
            return "Goodbye!"
        return (
            "I can help you calculate SIP returns. "
            "Try: 'Calculate SIP 5000 monthly for 10 years at 12%'"
        )

    # ------------------------------------------------------------------
    def _sip_calculator(self, monthly_amount, years, annual_rate, frequency=12):
        monthly_rate = annual_rate / (12 * 100)
        n = years * frequency
        if monthly_rate == 0:
            fv = monthly_amount * n
        else:
            fv = monthly_amount * (((1 + monthly_rate) ** n - 1) / monthly_rate) * (1 + monthly_rate)
        invested = monthly_amount * n
        returns = fv - invested
        return fv, invested, returns

    def _extract_and_calculate(self, text):
        monthly_amount = years = rate = None

        # Monthly amount
        for pattern in [
            r"(\d+(?:,\d{3})*)\s*(?:rupee|rs|rupees|₹|inr)?(?:\s+monthly|\s+per month|\s+every month)?",
            r"(?:sip|invest|investment)\s*(?:of\s*)?(\d+(?:,\d{3})*)",
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                monthly_amount = float(m.group(1).replace(",", ""))
                break

        # Duration
        for pattern in [r"(\d+)\s*(?:years?|yrs?)", r"for\s*(\d+)"]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                years = int(m.group(1))
                break

        # Rate
        for pattern in [
            r"(\d+(?:\.\d+)?)\s*(?:%|percent)",
            r"at\s*(\d+(?:\.\d+)?)",
            r"rate\s*(?:of\s*)?(\d+(?:\.\d+)?)",
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                rate = float(m.group(1))
                break

        # Validation
        missing = []
        if monthly_amount is None:
            missing.append("monthly amount")
        if years is None:
            missing.append("duration (years)")
        if rate is None:
            missing.append("expected return rate (%)")
        if missing:
            return (
                f"❌ Missing information: {', '.join(missing)}.<br>"
                "Example: 'Calculate SIP 5000 monthly for 10 years at 12%'"
            )

        fv, invested, returns = self._sip_calculator(monthly_amount, years, rate)

        return (
            f"📊 <b>SIP Investment Calculator</b><br><br>"
            f"💰 Monthly Investment: ₹{monthly_amount:,.2f}<br>"
            f"⏱️ Investment Period: {years} years ({years * 12} months)<br>"
            f"📈 Expected Return: {rate}% per annum<br><br>"
            f"<b>Results:</b><br>"
            f"💵 Total Invested: ₹{invested:,.2f}<br>"
            f"🎯 Maturity Value: ₹{fv:,.2f}<br>"
            f"💸 Returns Earned: ₹{returns:,.2f}<br>"
            f"📊 Returns: {(returns / invested) * 100:.2f}%<br><br>"
            f"<i>Note: Returns are estimated and subject to market risks.</i>"
        )