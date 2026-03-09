# 📘 SPY Vertical Spread Pricing Engine  
### *Sticky Strike • Intraday Modeling • Limit Order Optimization*

A lightweight, desk‑style pricing engine for **SPY vertical spreads**, designed for **intraday limit‑order decision making**.  
This tool computes:

- The **strikes** from expected move determined by the confidence level (**conf.** -> move -> strikes)
- The **implied volatilities** of each leg at the current spot price \(S₀\)  
- The **future value** of the vertical spread at a hypothetical spot \(S₁\)  
- A **spot ladder** showing how the spread behaves across multiple scenarios  
- Support for **short** and **long** vertical spreads 

The engine uses the **Sticky Strike** assumption — the most realistic model for repricing short‑dated SPY options over minutes to hours.

---

## 🎯 Why This Engine Exists

When trading short‑dated SPY vertical spreads, one of the most important questions is:

> **“If SPY moves to S₁ later today, what will my vertical spread be worth?”**

Most traders place limit orders with a vague sense of hope:

> *“I hope I get filled.”*

This engine turns that uncertainty into precision:

> **“I know what I’m asking for.”**

By computing the fair value of your vertical spread at a future spot price, the engine lets you set limit orders with intention rather than guesswork.

It does this by:

- Extracting IVs from real market bid/ask  
- Freezing those IVs (**Sticky Strike**)  
- Repricing each leg at the future spot \(S₁\)  
- Computing the vertical spread value under long/short positioning 

## 📁 Project Structure

The project is organized into modular components to easy management:
```text
spy_vertical_engine/
│
├── models/               # Pricing models & IV solver
│   ├── bsm.py            # Black–Scholes–Merton option pricing
│   ├── em_vix.py         # Expected move via VIX
|   ├── iv_solver.py      # Implied volatility root-finding
│
├── engine/               # Core vertical spread engine
│   ├── vertical_engine.py
│   ├── price_selection.py
│
├── utils/                # Market data & trading days
│   ├── data.py
│   ├── count_days.py
│   ├── option_chian.py
│
├── main.py               # CLI entry point
├── requirements.txt
└── .env                  # API keys (not committed)
```


## ⚙️ Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/baozh166/spy_vertical_engine.git
cd spy_vertical_engine
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Create a .env file
The engine requires a RapidAPI key for fetching VIX from CNBC.

Create a .env file in the project root:
```bash
echo "RAPIDAPI_CNBC_KEY=your_key_here" > .env
```


---

## 🚀 Running the Engine (CLI)

The CLI is powered by `main.py`.

### Example 1: Price the vertical spread at a specific S₁

```bash
python main.py \
    --expiration 2026-03-06 \
    --opt_type put \
    --position short \
    --spread_width 1 \
    --S1 680
```

### Example 2: Run a spot ladder
```bash
python main.py \
    --expiration 2026-03-06 \
    --opt_type call \
    --position short \
    --spread_width 1 \
    --ladder \
    --moves_pct -0.01 0 0.01
```

## 🧩 Key Features

- Real‑time SPY spot price (Yahoo Finance)  
- Real‑time VIX (CNBC RapidAPI), along with choosen confidence level, for computing expected move
- Automated strike selection based on expected move  
- Bid/ask‑aware IVs extraction at spot S₀ 
- Sticky Strike IV assumption 
- **At the time of spot S₀, Black‑Scholes repricing at potential spot S₁**
- Support for **short** and **long** vertical spreads
- Spot ladder scenario analysis  


## 🧠 Core Design Logic

### 1. **Compute IVs at the current spot price S₀**
For each leg (short and long), the engine:

1. Pulls the option’s **bid/ask** from the SPY option chain  
2. Computes the **implied volatility** using a Black‑Scholes root solver  
3. Stores:
   - `iv_short`
   - `iv_long`
   - `K_short`
   - `K_long`
   - `days_to_expiry`

These IVs represent the **market’s volatility surface at S₀**.

---

### 2. **Apply the Sticky Strike assumption**

Under Sticky Strike:

> **The IV at each strike stays constant even if SPY moves (<1.5%).**

This is realistic for:
- 0–5 DTE SPY options  
- Intraday moves  
- Small to moderate spot changes  
- Limit orders expected to fill within hours  

So when SPY moves from **S₀ → S₁**, the engine **reuses the same IVs**:

IV_short(S₁) = IV_short(S₀)

IV_long(S₁)  = IV_long(S₀)

---

### 3. **Reprice each leg at the future spot S₁**

Using the Black‑Scholes model:

p_short_bsm = BSM(S₁, K_short, iv_short)

p_long_bsm  = BSM(S₁, K_long, iv_long)

---

### 4. **Compute the vertical spread value at S₁**

For a **short vertical**:
vertical_value_at_s1 = -p_short_bsm + p_long_bsm

For a **long vertical**:
vertical_value_at_s1 =  p_short_bsm - p_long_bsm


This gives the **model value** of the spread at S₁, which can be used to:

- Set limit order credits  
- Estimate fill probability  
- Understand intraday risk  
- Visualize scenario PnL  

---

### 5. Spot Ladder (optional)

The engine includes a **spot ladder** that evaluates the vertical spread across multiple S₁ values:
S₁ = S₀ × (1 + pct_move)


This is extremely useful for:
 
- Understanding how spreads respond to spot changes  
- Planning limit orders based on expected intraday moves

---

## 📊 Pricing Workflow Diagram
<img width="1974" height="8192" alt="SPYOPP" src="https://github.com/user-attachments/assets/6c96610e-6aa2-47fd-b3f6-1461615729da" />

## 🔧 Arguments

| Argument | Type | Description |
|---------|------|-------------|
| `--expiration`, `-e` | str | Required. Option expiration date in `YYYY-MM-DD` format |
| `--rate`, `-r` | str | Option type: `call` or `put`, default = put |
| `--opt_type`, `-t` | str | Option type: `call` or `put`, default = put |
| `--position`, `-p` | str | Vertical spread position: `long` or `short`, default = short|
| `--spread_width`, `w` | float | Width of the vertical spread, used to determine the long strikes, default = 1 |
| `--confidence`, `c` | float | Confidence level (default=0.68) for expected move. The short strkies are 1 EM above/below spot S₀ |
| `--S1`, `-1` | float | Single future spot price for repricing |
| `--ladder`, `-d` | flag | Enables multiple spot points above/below S₀ for ladder repricing |
| `--moves_pct`, `-m` | float | Percentage move increments for spot ladder, default = -0.01 -0.005 0 0.005 0.01 |
| `--manual_hov`, `-s` | float | Manually input [bid ask last] for the HigherOptionValue (HOV) leg at SPY spot S0 |
| `--manual_lov`, `-l` | float | Manually input [bid ask last] for LowerOptionValue(LOV) leg at SPY spot S0 |

--manual_hov	Manual [bid ask last] for HOV leg
## 📈 Sample Output
```
==== Vertical Spread Value at S₁ ====
Option Type = put
Expiration = 2026-03-06
Confidence Level = 0.68
Vertical Spread Position = short
--------------------------------------------------
S0: 686.96
S1: 680.0
K_short: 671
K_long: 670
vertical_mkt_at_s0: -0.06
vertical_model_at_s1: -0.14
p_short_mkt: 0.89
p_long_mkt: 0.83
p_short_bsm: 2.15
p_long_bsm: 2.01
```
```
==== SPOT LADDER (Sticky Strike) ====
Underlying S0 = 686.96
Option Type = put
Expiration = 2026-03-06
Confidence Level = 0.68
vertical Spread Position = short
--------------------------------------------------------------------------------
      S1 |  K_short |   K_long |   Vertical mkt at S0 |   Vertical Value at S1
--------------------------------------------------------------------------------
  680.09 |      671 |      670 |                -0.06 |                  -0.13
  683.53 |      671 |      670 |                -0.06 |                  -0.08
  686.96 |      671 |      670 |                -0.06 |                  -0.05
  690.39 |      671 |      670 |                -0.06 |                  -0.02
  693.83 |      671 |      670 |                -0.06 |                  -0.01
--------------------------------------------------------------------------------
```

---

## Requirements
```
yfinance
pandas
pandas_market_calendars
scipy
python-dotenv
requests
```

## ⚠️ Limitations

- Sticky Strike is ideal for **intraday** modeling, not multi‑day horizons  
- Implied volatility extraction depends on bid/ask quality and may be noisy  
- No caching layer yet — Spot Ladder needs repeated data fetches
- RapidAPI CNBC endpoint may rate‑limit heavy usage  
- The model does not incorporate Sticky Delta, skew dynamics, or vol surface shifts  
- Black‑Scholes assumptions (lognormal returns, constant rates, no jumps) may understate tail behavior  

## 📄 License

This project is licensed under the **MIT License**.  
You are free to use, modify, distribute, and build upon this software, provided that the original license is included in any copies or substantial portions of the software.

## ⚡Disclaimer

This project is for **educational and research purposes only**.  
Nothing in this repository constitutes financial advice, trading advice, or a recommendation to buy or sell any security or derivative.  
Use the code and models at your own risk.





