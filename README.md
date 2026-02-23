# FinAssist — Virtual Finance Assistant

> A full-stack personal finance dashboard built with Python Flask, offering 15+ integrated tools for Indian retail investors — from live stock quotes and calculators to real-time market news and mutual fund search.

---

## ✨ Features

### 🔧 Tools & Calculators
| Tool | Description |
|------|-------------|
| **Stock Information** | Live NSE/BSE stock quotes with day high/low, 52-week range, weekly change, and company logo |
| **EMI Calculator** | Monthly EMI with full amortisation table, principal vs interest split bar, year-by-year breakdown |
| **SIP Calculator** | Systematic Investment Plan projection with year-by-year portfolio growth and wealth ratio |
| **Step-up SIP Calculator** | SIP with annual increment — compares against flat SIP and shows extra gain |
| **Fixed Deposit Calculator** | Maturity value with quarterly compounding, effective annual yield, year-by-year growth |
| **Zakat Calculator** | Islamic wealth tax calculator with live gold Nisab threshold, full asset breakdown, and payment schedule |
| **Mutual Fund Search** | Search 140+ top Direct-Growth funds by category — live NAV, 1Y/3Y/5Y returns via AMFI |

### 📊 Market Data
| Feature | Description |
|---------|-------------|
| **Currency Rates** | Live INR exchange rates for 10 currencies (USD, EUR, GBP, AED, SGD, JPY, CAD, AUD, CHF, CNY) via European Central Bank |
| **Gold & Silver Prices** | Live MCX futures prices (GC=F, SI=F) converted to INR — Gold per 10g, Silver per kg |
| **Market News** | Real-time finance news from 7 sources with parallel fetching, 24-hour filter, and source colour coding |

### 📚 Learn
| Feature | Description |
|---------|-------------|
| **Finance Glossary** | 80+ terms across 7 categories (Stocks, Valuation, Mutual Funds, Fixed Income, Loans, Tax, General) explained in plain beginner language |

---

## 🗂️ Project Structure

```
finassist/
├── app.py                  # Flask server — routes, stock data, news, metals, currency
├── market_data.py          # Nifty indices, gainers, losers, volume data
├── modules/
│   └── modules.py          # EMI, FD, SIP chatbot logic
├── templates/
│   └── chat_enhanced.html  # Main UI — single page application
├── static/
│   ├── style_enhanced.css  # All styles
│   └── stock_logos.json    # Company logo URLs
├── requirements.txt
└── README.md
```

---

## 🛠️ Tech Stack

### Backend
- **Python 3.10+**
- **Flask** — web framework and REST API
- **yfinance** — live stock and commodity prices (NSE, MCX futures)
- **requests** — HTTP client for external APIs
- **concurrent.futures** — parallel RSS feed fetching

### Frontend
- **HTML5 / CSS3 / JavaScript (ES6+)**
- **jQuery** — DOM manipulation and AJAX
- **Font Awesome** — icons
- **Google Fonts** (Plus Jakarta Sans)

### External APIs & Data Sources
| API | Used For |
|-----|----------|
| Yahoo Finance (yfinance) | NSE stocks, Gold (GC=F), Silver (SI=F) |
| Frankfurter API (ECB) | Live currency exchange rates |
| mfapi.in | Mutual fund NAV and returns (AMFI) |
| Economic Times RSS | Market news |
| Mint RSS | Market news |
| MoneyControl RSS | Market news |
| Business Standard RSS | Market news |
| Financial Express RSS | Market news |
| NDTV Profit RSS | Market news |
| Reuters RSS | Market news |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- pip

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/Bilal-03/finassist.git
cd finassist
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Run the app**
```bash
python app.py
```

**4. Open in browser**
```
http://localhost:5000
```

---

## 📦 Requirements

Create a `requirements.txt` with the following:

```
flask
yfinance
requests
```

No paid APIs or API keys required — everything runs on free public data sources.

---

## 📱 Screenshots Guide

To add your own screenshots:

1. Take screenshots of each feature
2. Create a `screenshots/` folder in the repo root
3. Save images as: `home.png`, `stock.png`, `emi.png`, `sip.png`, `metals.png`, `currency.png`, `news.png`, `mf.png`, `glossary.png`
4. Push to GitHub — the README will automatically display them

---

## 🔍 Key Implementation Details

- **Parallel news fetching** — All 7 RSS feeds are fetched simultaneously using `ThreadPoolExecutor`, so load time equals the slowest single feed rather than the sum of all
- **Server-side caching** — Mutual fund list cached for 6 hours to avoid repeated API calls
- **Client-side calculations** — EMI, SIP, FD, Zakat, and Step-up SIP are all computed in the browser with no backend call, making results instant
- **Finance-only news filter** — Two-pass keyword filter rejects non-finance content and requires at least one finance keyword, ensuring only relevant articles are shown
- **Live Nisab for Zakat** — Gold price fetched from MCX futures in real time to compute the Nisab threshold (85g gold standard) accurately

---

## 📊 Mutual Fund Categories Covered

Large Cap · Mid Cap · Small Cap · Flexi Cap · Multi Cap · Large & Mid Cap · ELSS (Tax Saving) · Hybrid · Index Fund · ETF · Sectoral / Thematic · Liquid · Short Duration · Gold / Commodities · International / FOF

All funds are **Direct Plan - Growth** only (no Regular or Dividend plans).

---

## 🙋 About

Built by **Bilal Choudhary** as a personal finance learning tool for Indian retail investors and beginners.

- 🔗 [LinkedIn](https://linkedin.com/in/bilal2012)
- 💻 [GitHub](https://github.com/Bilal-03)
- 📧 bilal3512@gmail.com

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
