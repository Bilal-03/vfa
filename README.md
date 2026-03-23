# VFA - Virtual Finance Assistant 🚀

**Your all-in-one platform for NSE Indian stocks, US stocks (NASDAQ/NYSE), SIP, EMI, mutual funds & more.**

A comprehensive Flask-based financial web application that combines real-time market data, AI-powered assistance, investment calculators, and portfolio management in one intelligent platform.

[![Live Demo](https://img.shields.io/badge/demo-live-success)](https://vfa-9tbs.onrender.com)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-2.0+-green.svg)](https://flask.palletsprojects.com/)

## ✨ Key Features

### 📊 **Live Market Data**
- **500+ Indian Stocks** - Real-time NSE price updates with 30-second refresh
- **10+ US Stocks** - Live NASDAQ and NYSE market data
- **Top Movers** - Track top gainers, losers, volume leaders, and value leaders
- **Currency Exchange** - Live INR to USD conversion rates with quick converter
- **Gold & Silver** - MCX futures prices for precious metals
- **Market News** - Latest financial news updates

### 💼 **Portfolio Management**
- **My Portfolio** - Track your holdings with live price updates
- **Add/Edit Holdings** - Manage stocks with quantity and average buy price
- **Real-time Valuation** - Automatic portfolio value calculation
- **Performance Tracking** - Monitor your investment gains/losses

### 🤖 **AI Chat Assistant**
- **Finance Q&A** - Ask anything about finance, investments, and markets
- **Tool Guidance** - Get help using any calculator or feature
- **Investment Tips** - AI-powered financial advice and insights

### 🧮 **Financial Calculators**
- **EMI Calculator** - Calculate home, car, and personal loan payments
- **SIP Calculator** - Project mutual fund returns with systematic investment planning
- **Step-up SIP** - Advanced SIP with annual increment planning
- **Fixed Deposit** - Calculate guaranteed FD returns and maturity amount
- **Zakat Calculator** - Islamic wealth tax calculator with live gold-based Nisab threshold

### 📈 **Mutual Funds**
- **MF Search** - Search any AMFI-registered Indian mutual fund
- **Live NAV** - Real-time Net Asset Value updates
- **Returns Analysis** - Historical performance data

### 📚 **Educational Resources**
- **Finance Glossary** - 100+ financial terms explained simply for beginners
- **Market Insights** - Learn about stocks, investments, and trading

## 🛠️ Tech Stack

- **Backend**: Python 3.8+, Flask
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **APIs**: 
  - NSE India API for stock data
  - Yahoo Finance for US stocks
  - Currency Exchange APIs
  - News APIs for market updates
- **AI Integration**: LLM-powered chat assistant
- **Data Processing**: Real-time market data aggregation
- **Deployment**: Render (configured via render.yaml)
- **Database**: Portfolio and user data management

## 📋 Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.8 or higher
- pip (Python package installer)
- Git

## ⚙️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Bilal-03/vfa.git
   cd vfa
   ```

2. **Create a virtual environment**
   ```bash
   # On Windows
   python -m venv venv
   venv\Scripts\activate

   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables** (if needed)
   ```bash
   # Create a .env file for API keys and configuration
   # Add your stock market API credentials
   ```

## 🏃‍♂️ Running the Application

### Quick Start

1. **Start the Flask development server**
   ```bash
   python app.py
   ```

2. **Access the application**
   Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

3. **Explore Features**
   - View live market data on the dashboard
   - Try the calculators (EMI, SIP, FD, Zakat)
   - Search for stocks and mutual funds
   - Add stocks to your portfolio
   - Chat with the AI assistant

### First-Time Setup Checklist

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed from requirements.txt
- [ ] Environment variables configured (API keys)
- [ ] Flask server running successfully
- [ ] Accessing localhost:5000 in browser

## 📁 Project Structure

```
vfa/
├── app.py                 # Main Flask application entry point
├── stock_routes.py        # Route handlers for stock operations
├── stock_service.py       # Business logic for stock data processing
├── market_data.py         # Market data API integration
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment configuration
├── .gitignore            # Git ignore patterns
├── modules/              # Custom Python modules
│   ├── calculators.py    # EMI, SIP, FD, Zakat calculators
│   ├── portfolio.py      # Portfolio management logic
│   ├── ai_chat.py        # AI assistant integration
│   └── news.py           # Market news fetching
├── static/               # Static assets
│   ├── css/
│   │   └── styles.css    # Custom styling
│   ├── js/
│   │   ├── market.js     # Market data updates
│   │   ├── portfolio.js  # Portfolio management
│   │   └── calculators.js # Calculator interactions
│   └── images/           # Images and icons
└── templates/            # HTML Jinja2 templates
    ├── index.html        # Main dashboard
    ├── chat.html         # AI chat interface
    ├── portfolio.html    # Portfolio view
    ├── calculators.html  # All calculators
    └── stocks.html       # Stock information page
```

## 🔑 Key Components

### 📱 **Main Dashboard**
The homepage features:
- Live market data widgets with 30-second auto-refresh
- Quick access to all tools and calculators
- Top gainers, losers, volume, and value stocks
- Currency and commodity prices
- Latest market news feed

### 💹 **Stock Information Module**
- Search Indian (NSE) and US stocks (NASDAQ/NYSE)
- Real-time price updates
- Daily and weekly performance metrics
- Historical data and trends

### 🤖 **AI Chat Mode**
Intelligent assistant that helps with:
- Financial queries and explanations
- Investment advice and strategies
- Tool usage guidance
- Market analysis and insights

### 💰 **Calculator Suite**

**EMI Calculator**
- Calculate monthly installments for loans
- Supports home loans, car loans, personal loans
- Shows total interest and payment breakup

**SIP Calculator**
- Project mutual fund investment returns
- Calculate wealth accumulation over time
- Visual representation of growth

**Step-up SIP Calculator**
- Advanced SIP with annual increment
- Higher returns through systematic increases
- Customizable step-up percentage

**Fixed Deposit Calculator**
- Calculate guaranteed FD returns
- Maturity amount projection
- Interest earned breakdown

**Zakat Calculator**
- Islamic wealth tax calculator
- Auto-calculated Nisab threshold (85g gold standard)
- Comprehensive asset and liability tracking
- 2.5% calculation on qualifying wealth

### 📊 **Portfolio Management**
- Add and track stock holdings
- Live price updates (30-second refresh)
- Automatic profit/loss calculation
- Support for both Indian and US stocks

### 📰 **Market Intelligence**
- **Live Currency Rates**: Real-time forex data with quick converter
- **Gold & Silver Prices**: MCX futures tracking
- **Market News**: Latest financial news aggregation
- **Top Movers**: Real-time tracking of market leaders

### 📚 **Educational Resources**
- **Finance Glossary**: 100+ terms explained simply
- Clear definitions for beginners
- Searchable database of financial concepts

## 🌐 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard with live market data |
| `/chat` | GET/POST | AI chat interface for financial assistance |
| `/stock` | GET/POST | Search and display stock information |
| `/portfolio` | GET/POST | Portfolio management and tracking |
| `/mutual-funds` | GET | Mutual fund search and data |
| `/calculators/emi` | GET/POST | EMI calculator |
| `/calculators/sip` | GET/POST | SIP calculator |
| `/calculators/stepup-sip` | GET/POST | Step-up SIP calculator |
| `/calculators/fd` | GET/POST | Fixed deposit calculator |
| `/calculators/zakat` | GET/POST | Zakat calculator |
| `/api/market-data` | GET | Live market data (JSON) |
| `/api/currency` | GET | Currency exchange rates |
| `/api/commodities` | GET | Gold & silver prices |
| `/api/news` | GET | Market news feed |
| `/api/portfolio` | POST | Add/update portfolio holdings |
| `/glossary` | GET | Finance terms and definitions |

## 🎨 User Interface Features

- **Modern, Clean Design**: Professional financial dashboard aesthetic
- **Responsive Layout**: Seamless experience on desktop, tablet, and mobile devices
- **Real-time Updates**: Live data refresh without page reload
- **Interactive Widgets**: 
  - Top gainers/losers with live updates
  - Currency converter with instant conversion
  - Portfolio value tracker
  - Market news carousel
- **Smooth Navigation**: Easy access to all tools via intuitive menu
- **Dark/Light Themes**: Comfortable viewing in any environment
- **Form Validation**: Smart input validation for all calculators
- **Live Indicators**: Visual indicators for market status (LIVE badges)
- **Auto-refresh**: Market data updates every 30 seconds

## 🌟 Unique Features

### 1. **Comprehensive Coverage**
- 500+ Indian stocks from NSE
- US stocks from NASDAQ and NYSE
- All AMFI-registered mutual funds
- Multi-market support in one platform

### 2. **AI-Powered Assistance**
- Natural language finance queries
- Context-aware responses
- Tool recommendations
- Investment guidance

### 3. **Islamic Finance Support**
- Dedicated Zakat calculator
- Live gold price-based Nisab calculation
- Comprehensive asset and liability tracking
- Shariah-compliant wealth management

### 4. **Advanced Calculators**
- Step-up SIP with annual increments
- Detailed EMI breakdowns
- Multi-scenario FD planning
- Real-time currency conversion

### 5. **Portfolio Tracking**
- Multi-market portfolio (NSE + US stocks)
- Live profit/loss calculation
- Easy holding management
- Real-time valuation updates

## 🚀 Deployment

### Live Demo

The application is live at: **[https://vfa-9tbs.onrender.com](https://vfa-9tbs.onrender.com)**

### Deploying to Render

This project is configured for deployment on Render:

1. Push your code to GitHub
2. Connect your repository to Render
3. The `render.yaml` file contains the deployment configuration
4. Add environment variables in Render dashboard
5. Render will automatically build and deploy your application

### Local Development

For local development with hot reload:
```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python app.py
```

## 📖 Usage Guide

### Getting Started

1. **Explore the Dashboard**: View live market data, top movers, currency rates, and news
2. **Search Stocks**: Use the stock information tool to look up any NSE or US stock
3. **Build Your Portfolio**: Add your holdings to track real-time performance
4. **Use Calculators**: Calculate EMI, SIP, FD returns, or Zakat obligations
5. **Ask AI**: Use chat mode for any finance-related questions

### Example Use Cases

**For Investors:**
- Track your portfolio performance in real-time
- Calculate SIP returns before starting investments
- Search mutual funds and compare NAVs
- Stay updated with market news

**For Loan Seekers:**
- Calculate EMI for home, car, or personal loans
- Compare different loan tenures and interest rates
- Plan your monthly budget

**For Muslim Investors:**
- Calculate Zakat on your wealth
- Track assets and liabilities
- Auto-updated Nisab threshold based on gold prices

**For Beginners:**
- Learn financial terms from the glossary
- Ask AI assistant for investment guidance
- Understand SIP and compound interest with calculators

### Environment Variables

Set the following environment variables in your deployment platform or `.env` file:

```bash
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# API Keys (add your actual keys)
NSE_API_KEY=your-nse-api-key
YAHOO_FINANCE_KEY=your-yahoo-finance-key
CURRENCY_API_KEY=your-currency-api-key
NEWS_API_KEY=your-news-api-key
AI_ASSISTANT_KEY=your-ai-api-key

# Database (if using)
DATABASE_URL=your-database-url

# Optional
DEBUG=False
PORT=5000
```

## 📊 Feature Details

### 💼 Portfolio Management
Track your investments across multiple markets:
- **Add Holdings**: Input stock symbol, quantity, and average buy price
- **Live Updates**: Automatic price refresh every 30 seconds
- **Performance Metrics**: Real-time P&L calculation
- **Multi-Currency**: Support for both ₹ (INR) and $ (USD) stocks

### 📈 Market Data Dashboard
Comprehensive market overview:
- **Top Gainers**: Stocks with highest percentage gains
- **Top Losers**: Stocks with biggest declines
- **Top Volume**: Most actively traded stocks
- **Top Value**: Highest value traded stocks
- **Auto-refresh**: Updates every 30 seconds with LIVE indicators

### 💱 Currency & Commodities
- **Live Currency Rates**: Real-time INR/USD exchange rates
- **Quick Converter**: Instant currency conversion tool
- **Gold Prices**: MCX gold futures (live)
- **Silver Prices**: MCX silver futures (live)
- **Refresh Option**: Manual update button for latest rates

### 📰 Market News
- Latest financial news aggregation
- Regular updates on market movements
- Relevant news for Indian and global markets
- One-click refresh for newest stories

### 🧮 Calculators Deep Dive

**EMI Calculator**
- Input: Loan amount, interest rate, tenure
- Output: Monthly EMI, total interest, total payment
- Use cases: Home loans, car loans, personal loans

**SIP Calculator**
- Input: Monthly investment, expected return, period
- Output: Future value, total investment, wealth gained
- Visual growth projection

**Step-up SIP Calculator**
- Input: Starting SIP, annual step-up %, expected return, period
- Output: Future value with incremental investments
- Comparison with regular SIP

**Fixed Deposit Calculator**
- Input: Principal amount, interest rate, tenure
- Output: Maturity amount, interest earned
- Quarterly compounding calculations

**Zakat Calculator**
- Automatic Nisab calculation using live gold prices (85g standard)
- Asset tracking: Cash, investments, stocks, MFs, gold, silver
- Liability deduction: Loans and debts
- 2.5% calculation on qualifying net wealth

### 🔍 Stock Information
- Search by stock name or ticker symbol
- Support for NSE, NASDAQ, and NYSE
- Real-time price data
- Daily and weekly performance views
- Historical data visualization

### 📚 Finance Glossary
- 100+ financial terms and concepts
- Simple explanations for beginners
- Searchable database
- Categories: Stocks, Mutual Funds, Banking, Trading, etc.

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 Development Guidelines

- Follow PEP 8 style guide for Python code
- Write meaningful commit messages
- Add comments for complex logic
- Update documentation for new features
- Test thoroughly before submitting PRs

## 🐛 Known Issues

- Check the [Issues](https://github.com/Bilal-03/vfa/issues) page for current bugs and feature requests

## 📈 Future Enhancements

- [ ] **Advanced Charting**: Technical indicators and candlestick charts
- [ ] **Price Alerts**: Email/SMS notifications for price movements
- [ ] **User Authentication**: Personalized accounts and saved preferences
- [ ] **Multiple Portfolios**: Create and manage separate portfolios
- [ ] **Tax Calculator**: Capital gains tax calculation
- [ ] **Dividend Tracker**: Dividend income tracking and projection
- [ ] **Comparison Tools**: Side-by-side stock and MF comparison
- [ ] **Export Features**: Download portfolio and calculator results as PDF/Excel
- [ ] **Mobile App**: Native Android/iOS applications
- [ ] **Watchlist**: Save favorite stocks for quick monitoring
- [ ] **Advanced AI**: More sophisticated financial planning assistance
- [ ] **News Alerts**: Personalized news based on portfolio
- [ ] **Goal-based Planning**: SIP planning for specific financial goals
- [ ] **Retirement Calculator**: Retirement corpus planning tool
- [ ] **Insurance Calculator**: Life and health insurance need assessment
- [ ] **Multi-language Support**: Hindi and other regional languages
- [ ] **Social Features**: Share insights and strategies with community
- [ ] **Backtesting**: Test investment strategies with historical data

## 🔒 Security

- Never commit API keys or sensitive credentials
- Use environment variables for configuration
- Keep dependencies updated
- Follow security best practices

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 👤 Author

**Bilal-03**
- GitHub: [@Bilal-03](https://github.com/Bilal-03)

## 🙏 Acknowledgments

- Flask framework and community
- Stock market data providers
- Bootstrap for UI components
- All contributors and supporters

## ❓ FAQ

**Q: Is the market data real-time?**  
A: Yes, the application fetches live data from NSE, NASDAQ, and NYSE with 30-second auto-refresh intervals.

**Q: Which stocks are supported?**  
A: 500+ Indian stocks from NSE and 10+ major US stocks from NASDAQ and NYSE. The list is regularly updated.

**Q: Is my portfolio data saved?**  
A: Currently, portfolio data is session-based. User authentication with persistent storage is planned for future releases.

**Q: How accurate are the calculators?**  
A: All calculators use industry-standard formulas. However, actual returns may vary based on market conditions.

**Q: What is the Nisab calculation based on?**  
A: Nisab is calculated using the live gold price standard of 85 grams of gold, automatically updated.

**Q: Can I use this for actual trading?**  
A: VFA is an informational and educational platform. It does not facilitate actual trading or transactions.

**Q: Is the AI financial advice reliable?**  
A: The AI assistant provides general guidance and information. Always consult a certified financial advisor for personalized investment decisions.

## 🔧 Troubleshooting

**Market data not loading:**
- Check your internet connection
- Try refreshing the page
- The free APIs may have rate limits; wait a few minutes

**Calculator not working:**
- Ensure all required fields are filled
- Check that numeric values are entered correctly
- Verify that percentage values are between 0-100

**Portfolio not updating:**
- Check if the stock symbol is correct
- Ensure the market is open (for live prices)
- Try using the refresh button

**Slow performance:**
- Clear browser cache
- Disable browser extensions
- Check internet speed

## 📞 Support

If you encounter any issues or have questions:
- Open an issue on [GitHub Issues](https://github.com/Bilal-03/vfa/issues)
- Check existing documentation in this README
- Review closed issues for solutions
- Visit the [live demo](https://vfa-9tbs.onrender.com) to test features

## ⭐ Show Your Support

Give a ⭐️ if this project helped you!

---

## 🎯 Project Goals

Virtual Finance Assistant aims to democratize financial information and tools, making them accessible to everyone regardless of their financial literacy level. We believe in:

- **Financial Inclusion**: Providing free tools for everyone
- **Education First**: Teaching concepts alongside calculations
- **Transparency**: Open-source code and clear methodologies
- **Accessibility**: Simple interface for all user levels
- **Islamic Finance**: Supporting Shariah-compliant calculations

## 🏆 Achievements

- ✅ 500+ Indian stocks supported
- ✅ Multi-market coverage (NSE, NASDAQ, NYSE)
- ✅ Real-time data updates
- ✅ AI-powered assistance
- ✅ 5+ financial calculators
- ✅ Islamic finance support
- ✅ Live currency and commodity tracking
- ✅ Portfolio management
- ✅ Comprehensive finance glossary

## 📊 Technical Highlights

- **Low Latency**: 30-second refresh rate for live data
- **Scalable Architecture**: Modular Flask application
- **API Integration**: Multiple data sources aggregated
- **Responsive Design**: Mobile-first approach
- **Clean Code**: Well-documented and maintainable
- **Production Ready**: Deployed on Render with auto-scaling

---

**⚠️ Important Disclaimer**: 

This application is designed for **educational and informational purposes only**. Virtual Finance Assistant provides tools and information to help users make informed decisions, but:

- 📊 **Not Financial Advice**: Information provided should not be considered as professional financial, investment, tax, or legal advice
- 💼 **Consult Professionals**: Always consult qualified financial advisors, tax consultants, or certified planners before making investment decisions
- 📉 **Market Risk**: Investments in stocks and mutual funds are subject to market risks. Past performance does not guarantee future returns
- 🔢 **Calculator Accuracy**: While calculations use standard formulas, actual results may vary based on specific circumstances and market conditions
- 🕌 **Islamic Rulings**: For Zakat and other Islamic finance matters, please consult a qualified Islamic scholar
- 🚫 **No Trading**: This platform does not facilitate actual trading or transactions
- 📱 **Data Accuracy**: While we strive for accuracy, real-time data may have delays or discrepancies

**The developers and maintainers of VFA are not liable for any financial decisions made based on information from this platform.**
