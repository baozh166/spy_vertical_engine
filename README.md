# SPY Vertical Spread Pricing Engine (Sticky Strike Model)

This project implements a desk‑style options pricing engine for **SPY 5‑DTE vertical spreads**, designed specifically for traders who place **limit orders** and expect fills within **minutes to a few hours**.  
The engine computes:

- The **implied volatilities** of each leg at the current spot price **S₀**
- The **future value** of the vertical spread at a hypothetical spot price **S₁**
- A **spot ladder** showing how the spread behaves across multiple S₁ scenarios

The core of the engine is the **Sticky Strike assumption**, which is the most realistic model for short‑dated SPY options over intraday horizons.

---

## 🔍 Why This Engine Exists

When selling (or buying) short‑dated vertical spreads, traders often want to know:

> **“If SPY moves to S₁ later today, what will my vertical spread be worth?”**

This engine answers that question precisely.

It computes the **vertical spread value at S₁**, using the **same implied volatilities measured at S₀**, which is exactly how real market makers approximate intraday repricing for short‑dated options.

---

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
- 0–7 DTE SPY options  
- Intraday moves  
- Small to moderate spot changes  
- Limit orders expected to fill within hours  

So when SPY moves from **S₀ → S₁**, the engine **reuses the same IVs**:
IV_short(S₁) = IV_short(S₀)
IV_long(S₁)  = IV_long(S₀)
No skew reshaping. No surface shifting.  
Just pure Sticky Strike.

---

### 3. **Reprice each leg at the future spot S₁**

Using the Black‑Scholes model:
p_short_bsm = BSM(S1, K_short, iv_short)
p_long_bsm  = BSM(S1, K_long, iv_long)

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

## 📈 Spot Ladder

The engine includes a **spot ladder** that evaluates the vertical spread across multiple S₁ values:
S₁ = S₀ × (1 + pct_move)



This is extremely useful for:

- Visualizing delta/gamma behavior  
- Understanding how spreads respond to spot changes  
- Planning limit orders based on expected intraday moves  

---

## 🧩 Class‑Based Architecture

The entire engine is wrapped in a single class:


It handles:

- Market data retrieval  
- VIX retrieval  
- Expected move calculation  
- Strike selection  
- IV computation  
- BSM repricing  
- Vertical spread valuation  
- Spot ladder generation  

This makes the engine easy to reuse, extend, and integrate into trading workflows.

---

## 🛠 Key Features

- Real‑time SPY spot price  
- Real‑time VIX via CNBC API  
- Automated strike selection based on expected move  
- Bid/ask‑aware IV extraction  
- Sticky Strike repricing  
- Full Black‑Scholes implementation  
- Spot ladder scenario analysis  
- Support for **long** and **short** vertical spreads  
- Clean class‑based design  

---

## 🚀 Example Usage

```python
engine = VerticalEngine(
    rapidapi_key_cnbc=rapidapi_key,
    expiration="2026-03-06",
    rate=0.04,
    opt_type="call",
    spread_width=1,
    confidence=0.68,
)

# Compute vertical value at a future spot S1
result = engine.vertical_value_sticky_strike(S1=505)

# Generate a spot ladder
engine.spot_ladder(pct_moves=[-0.01, -0.005, 0, 0.005, 0.01])






