# Deploy to Free Cloud (Render) - Step by Step

## Option 1: Render.com (FREE - Easiest)

### Step 1: Prepare Your Code
The code is already ready! You just need to push it to GitHub.

### Step 2: Push to GitHub
```bash
# Initialize git if not already
cd D:/polymarket_ai_bot
git init
git add .
git commit -m "Polymarket AI Trading Bot"

# Create GitHub repo and push
# (You'll need a GitHub account)
```

### Step 3: Deploy to Render
1. Go to [render.com](https://render.com) and sign up
2. Click "New" → "Web Service"
3. Connect your GitHub and select this repo
4. Configure:
   - Name: `polymarket-trader`
   - Environment: `Python`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python quant_trader.py`
5. Add Environment Variables:
   - `POLY_BUILDER_KEY`: `019d2b2f-b867-7daf-ac0b-92da916743fd`
   - `POLY_BUILDER_SECRET`: `g8_tldos1eNeC1Ri6Itnaz49ibSBRCQKhYQCgK30qos=`
   - `POLY_BUILDER_PASSPHRASE`: `bd017fc2ea140a60e42763d2383935fa6dd33b0d972ba08f7bf96d0c5cc41059`
6. Click "Deploy"

**Free Tier:** 750 hours/month, sleeps after 15 min inactivity

---

## Option 2: Fly.io (FREE - More Features)

### Step 1: Install Fly CLI
```bash
# Windows (in PowerShell)
winget install flyctl

# Or use npm
npm install -g flyctl
```

### Step 2: Deploy
```bash
fly auth login
fly launch
fly deploy
```

---

## Option 3: Railway (Free Trial)

### Step 1: Sign up at [railway.app](https://railway.app)

### Step 2: Deploy
```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

---

## Quick Comparison

| Platform | Free Hours | Sleep | Best For |
|----------|------------|-------|----------|
| **Render** | 750/month | Yes | Beginners |
| **Fly.io** | 3 apps | No | Always on |
| **Railway** | $5 credit | No | Quick test |

---

## What Happens When Deployed?

The cloud server will:
1. Run the Quant Trading Engine 24/7
2. Run the Professional Analyst
3. Save all data to server storage
4. You can access via public URL

---

## Important Notes

1. **API Keys**: Store them in environment variables on the cloud
2. **Data Persistence**: Files may be deleted on restart (use database)
3. **Free Limitations**: Services sleep after inactivity on Render

---

## Need Help?

Say "yes" and I'll help you:
1. Set up GitHub account
2. Push code to GitHub
3. Deploy to Render step by step