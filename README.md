# FinAssist — Virtual Finance Assistant

> A full-stack personal finance dashboard built with Python Flask — offering 20+ integrated tools for Indian retail investors, from live stock quotes and AI chat to portfolio tracking, SIP/EMI calculators, mutual fund search, and real-time market data. Fully responsive with a dedicated mobile interface that auto-detects your device.

---

## ✨ Features

### 🤖 AI Chat
Powered by **Groq (LLaMA 3.1 8B Instant)** — ask anything about NSE/BSE stocks, SIP, mutual funds, EMI, taxes, or personal finance. Automatically enriches responses with live stock data when the query involves a stock or ticker.

### 📈 Stock Intelligence
| Feature | Description |
|---------|-------------|
| **Live Quotes** | NSE/BSE Indian stocks + US stocks (NASDAQ/NYSE) — price, change, day high/low |
| **Weekly Performance** | Week open/close, high/low, and % change |
| **Candlestick Charts** | Interactive price charts — 1D, 1W, 1M, 3M, 6M, 1Y, 5Y, MAX timeframes |
| **Company Profiles** | Name, sector, logo, and key financial metrics |
| **Smart Symbol Resolver** | Type a company name or partial ticker — auto-resolves to the correct NSE/US symbol |

### 💼 Portfolio Tracker
| Feature | Description |
|---------|-------------|
| **Cloud Sync via Supabase** | Portfolio stored server-side — access from any device, any browser |
| **Username Identity** | No sign-up or password required — just pick a username to save and retrieve your portfolio |
| **Live P&L** | Real-time profit/loss per holding and overall totals |
| **Mixed Currency Support** | Handles Indian (₹) and US ($) stocks in the same portfolio with live USD/INR conversion |
| **Holdings Management** | Add, edit, and remove holdings with quantity and average buy price |

### 🔧 Calculators
| Tool | Description |
|------|-------------|
| **EMI Calculator** | Monthly EMI with full amortisation table, principal vs. interest split, year-by-year breakdown |
| **SIP Calculator** | Systematic Investment Plan projection with year-by-year portfolio growth and wealth ratio |
| **Step-up SIP** | SIP with annual increment — compares against flat SIP and shows extra gain |
| **Fixed Deposit** | Maturity value with quarterly compounding, effective annual yield, year-by-year table |
| **Zakat Calculator** | Islamic wealth tax with live gold Nisab threshold, full asset breakdown, and payment schedule |

### 📊 Market Data
| Feature | Description |
|---------|-------------|
| **Live Indices Ticker** | Continuous scrolling ticker — NIFTY 50, SENSEX, NIFTY BANK, NIFTY IT, NIFTY AUTO, NIFTY MIDCAP 100, NIFTY SMALLCAP 250 |
| **Top Gainers / Losers** | Real-time NSE top movers by price change |
| **Volume & Turnover Leaders** | NSE top stocks by trading volume and turnover value |
| **Currency Rates** | Live INR exchange rates for 10 currencies via European Central Bank with quick converter |
| **Gold & Silver Prices** | Live MCX futures (GC=F, SI=F) in INR — Gold per 10g, Silver per kg |
| **Market News** | Real-time finance news from 7 sources with parallel fetching, 24-hour filter, and colour-coded source tags |

### 📦 Mutual Funds
Search 1,000+ Direct Growth funds by name or category. Shows live NAV, 1Y/3Y/5Y returns, and an investment growth simulator.

**Categories:** Large Cap · Mid Cap · Small Cap · Flexi Cap · Multi Cap · Large & Mid Cap · ELSS · Hybrid · Index Fund · ETF · Sectoral/Thematic · Liquid · Short Duration · Gold/Commodities · International/FOF

### 📚 Finance Glossary
80+ terms across 7 categories — Stocks, Valuation, Mutual Funds, Fixed Income, Loans, Tax & Regulation, and General — explained in plain beginner language with category filtering and search.

---

## 📱 Responsive Design — Desktop + Mobile

FinAssist auto-detects your device on the server side and serves the right interface — no client-side redirect or flash:

| Device | Interface |
|--------|-----------|
| **Desktop / Laptop** | Full sidebar navigation, panel-based layout, table-style portfolio view |
| **Mobile / Tablet** | Native app-style bottom navigation, full-screen screens, card-based portfolio, touch-optimised |

The mobile interface has a dedicated `/portfolio` page with a slide-up bottom sheet modal and a scrollable card layout. One Flask server handles everything.

---

## 🗂️ Project Structure

```
finassist/
├── app.py                             # Flask server — all routes, AI, stock data, news, metals, currency
├── market_data.py                     # NSE indices, gainers, losers, volume, turnover
├── stock_routes.py                    # Stock Intelligence API blueprint (/si/*)
├── stock_service.py                   # Stock data service layer with caching
├── modules/
│   └── modules.py                     # EMI, FD, SIP bot module
├── templates/
│   ├── chat_enhanced.html             # Desktop UI — sidebar single-page app
│   ├── chat_mobile.html               # Mobile UI — bottom nav, screen-based layout
│   └── portfolio_mobile.html          # Dedicated mobile portfolio page (/portfolio)
├── static/
│   ├── style_enhanced.css             # Desktop styles
│   ├── style_mobile.css               # Mobile styles
│   ├── stock_dashboard.js             # Stock charts and intelligence panel
│   ├── stock_dashboard.css            # Stock dashboard styles
│   ├── portfolio_watchlist.js         # Desktop portfolio tracker
│   └── portfolio_watchlist_mobile.js  # Mobile portfolio tracker
├── .env                               # Environment variables (not committed)
├── render.yaml                        # Render.com deployment config
└── requirements.txt
```

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **Python 3.11** | Language |
| **Flask** | Web framework and REST API |
| **yfinance** | Live stock and commodity prices (NSE, MCX futures) |
| **Groq SDK** | AI chat — LLaMA 3.1 8B Instant (free tier) |
| **Supabase** | Cloud PostgreSQL for portfolio persistence |
| **requests / curl_cffi** | HTTP clients — external APIs and NSE scraping |
| **BeautifulSoup4 / lxml** | RSS feed parsing for news |
| **concurrent.futures** | Parallel RSS feed fetching |
| **python-dotenv** | Environment variable management |
| **gunicorn** | Production WSGI server |

### Frontend
| Technology | Purpose |
|------------|---------|
| **HTML5 / CSS3 / JavaScript (ES6+)** | UI |
| **jQuery** | DOM manipulation and AJAX |
| **Font Awesome 6** | Icons |
| **Google Fonts** (Plus Jakarta Sans) | Typography |
| **Lightweight Charts v4** | Candlestick and price charts |

### External APIs & Data Sources
| API / Source | Used For |
|-------------|----------|
| Groq API | AI chat (LLaMA 3.1 8B Instant, free tier available) |
| Supabase | Portfolio cloud storage |
| NSE India API | Live indices, gainers, losers, volume, turnover |
| Yahoo Finance (yfinance) | NSE/US stock quotes, Gold (GC=F), Silver (SI=F) |
| Frankfurter (ECB) | Live currency exchange rates — free, no key needed |
| mfapi.in | Mutual fund NAV and returns (AMFI data) — free |
| Economic Times RSS | Market news |
| MoneyControl RSS | Market news |
| Mint RSS | Market news |
| Business Standard RSS | Market news |
| Financial Express RSS | Market news |
| NDTV Profit RSS | Market news |
| Reuters RSS | Market news |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- A free [Groq API key](https://console.groq.com) — for AI chat
- A free [Supabase](https://supabase.com) project — for portfolio cloud sync

### 1. Clone the repository
```bash
git clone https://github.com/Bilal-03/finassist.git
cd finassist
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Create a `.env` file in the project root
```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-public-key
GROQ_API_KEY=gsk_your-groq-api-key
FLASK_SECRET_KEY=any-random-secret-string
```

### 4. Set up Supabase tables
Run this SQL in your Supabase **SQL Editor**:

```sql
create table users (
  username text primary key,
  created_at bigint
);

create table portfolios (
  username text,
  symbol   text,
  qty      float,
  avg_price float,
  added_at  bigint,
  primary key (username, symbol)
);
```

### 5. Run the app
```bash
python app.py
```

### 6. Open in browser
```
http://localhost:5000            ← auto-detects device (desktop or mobile)
http://localhost:5000/portfolio  ← dedicated mobile portfolio page
```

To test the mobile layout on your desktop, use browser DevTools device mode (F12 → toggle device toolbar).

### 7. Access from your phone (same Wi-Fi)
```bash
# Find your laptop IP
ifconfig | grep "inet "          # macOS/Linux
ipconfig                         # Windows

# Then open on phone:
http://192.168.x.x:5000
```

---

## 📦 requirements.txt

```
Flask
pandas
openpyxl
yfinance
requests
SpeechRecognition
pyttsx3
beautifulsoup4
lxml
gunicorn
python-dotenv
google-generativeai
groq
supabase
curl_cffi>=0.7.0
```

---

## ☁️ Deployment on Render.com

The project includes a `render.yaml` for one-click deployment:

1. Push your code to a GitHub repository
2. Go to [Render](https://render.com) → **New Web Service** → connect your repo
3. Add these environment variables in the Render dashboard:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `GROQ_API_KEY`
   - `FLASK_SECRET_KEY`
4. Deploy — Render uses gunicorn automatically via the `render.yaml` config

The start command used is:
```
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
```

---

## 🔍 Key Implementation Details

- **Automatic device detection** — Server-side User-Agent parsing routes desktop users to `chat_enhanced.html` and mobile/tablet users to `chat_mobile.html`. No JavaScript redirect or flash of wrong layout.

- **Smart market data caching** — NSE indices are cached server-side for 60 seconds. If NSE's API fails due to rate limiting, the last successful full result is served instead of degrading to Yahoo Finance's limited 2-index fallback — ensuring the ticker always shows all 7 indices on both desktop and mobile.

- **AI with live stock context** — Before passing a query to Groq, the server detects if it's stock-related and injects live price data as context. The AI always answers with current numbers rather than stale training data.

- **Parallel news fetching** — All 7 RSS feeds are fetched simultaneously using `ThreadPoolExecutor`. Total load time equals the slowest single feed, not the sum of all seven.

- **Finance-only news filter** — A two-pass keyword filter first rejects non-finance content (cricket, Bollywood, weather, politics) then requires at least one finance keyword, ensuring clean and relevant results.

- **Server-side caching** — Mutual fund list cached for 6 hours; market indices cached for 60 seconds; individual stock data cached in `stock_service.py` to reduce yfinance API calls.

- **Client-side calculations** — All calculator logic (EMI, SIP, Step-up SIP, FD, Zakat) runs entirely in the browser with no backend call, making results instant.

- **Live Nisab for Zakat** — Current gold price fetched from MCX futures (GC=F) at calculation time to compute the Nisab threshold (85g gold standard) with today's price, not a hardcoded estimate.

- **Portfolio cloud sync** — Supabase stores holdings by username. No passwords or sign-up — just a username. Access the same portfolio from desktop and phone seamlessly.

- **Two separate portfolio renderers** — `portfolio_watchlist.js` (desktop) renders a full data table with row-level actions. `portfolio_watchlist_mobile.js` renders cards optimised for touch with View / Edit / Remove buttons. Both share the same Flask API endpoints.

---

## 🗺️ API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main app — auto-routes by device |
| GET | `/portfolio` | Dedicated mobile portfolio page |
| POST | `/get` | AI chat response |
| GET | `/market` | All NSE indices (60s server cache) |
| GET | `/top_gainers` | NSE top gainers |
| GET | `/top_losers` | NSE top losers |
| GET | `/top_volume` | NSE top stocks by volume |
| GET | `/top_turnover` | NSE top stocks by turnover |
| GET | `/currency` | Live INR exchange rates |
| GET | `/metals` | Live gold & silver prices |
| GET | `/news` | Market news (parallel fetch, 7 sources) |
| GET | `/mf_list` | Full mutual fund list (6h cache) |
| GET | `/mf_detail/<code>` | Fund NAV, returns, and growth data |
| GET | `/si/quote` | Live stock quote |
| GET | `/si/profile` | Company profile and logo |
| GET | `/si/candle` | Candlestick OHLCV data |
| GET | `/si/metrics` | Financial metrics |
| GET | `/si/analyst` | Analyst ratings |
| GET | `/si/news` | Stock-specific news |
| POST | `/api/portfolio/identify` | Log in / create username |
| GET | `/api/portfolio/load` | Load all holdings for a user |
| POST | `/api/portfolio/save` | Add or update a holding |
| POST | `/api/portfolio/delete` | Remove a holding |
| POST | `/api/portfolio/sync` | Full portfolio replace/sync |
| GET | `/health` | Health check endpoint |

---

## 🙋 About

Built by **Bilal Choudhary** as a personal finance learning tool for Indian retail investors and beginners who want a single place to track investments, run calculations, and get quick AI-powered answers.

- 🔗 [LinkedIn](https://linkedin.com/in/bilal2012)
- 💻 [GitHub](https://github.com/Bilal-03)
- 📧 bilal3512@gmail.com

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).