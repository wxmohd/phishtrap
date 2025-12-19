# 🎣 Phishing Email Generator - Outlook Mode

Generate realistic phishing emails from your 2 test accounts to test PhishTrap!

## 📋 **Setup**

### **1. Set Passwords (Environment Variables)**

```bash
export OUTLOOK_PHISH1_PASSWORD='your_password_for_phishing_testt1'
export OUTLOOK_PHISH2_PASSWORD='your_password_for_phishing_testt2'
```

### **2. Run the Generator**

```bash
cd /home/osboxes/phishtrap/scripts
python3 generate_phishing_emails.py --mode outlook --count 10
```

---

## 🚀 **Usage Examples**

### **Generate 10 Phishing Emails (Mixed)**
```bash
python3 generate_phishing_emails.py --mode outlook --count 10
```

### **Generate 20 Phishing Emails (No Legit)**
```bash
python3 generate_phishing_emails.py --mode outlook --no-legit --count 20
```

### **Generate 5 Emails for Quick Test**
```bash
python3 generate_phishing_emails.py --mode outlook --count 5
```

---

## 📧 **How It Works**

1. **Rotates Between Accounts:**
   - Email 1 → `phishing_testt1@outlook.com`
   - Email 2 → `phishing_testt2@outlook.com`
   - Email 3 → `phishing_testt1@outlook.com`
   - Email 4 → `phishing_testt2@outlook.com`
   - ... and so on

2. **Sends to Target:**
   - All emails go to: `d3m01231@outlook.com`

3. **Auto-Sync:**
   - PhishTrap background sync picks them up within 60 seconds
   - Dashboard updates in real-time via WebSocket

---

## 🎯 **What Gets Generated**

### **Phishing Templates:**
- PayPal account limited
- Amazon order shipped
- Bank account verification
- Lottery winner
- Microsoft security code
- IRS tax refund
- Package delivery failed
- LinkedIn profile views
- Netflix payment failed
- Apple ID locked

### **Legitimate Templates (if not using --no-legit):**
- Newsletter updates
- Meeting reminders

---

## 📊 **Example Output**

```
🎣 Generating 10 phishing emails for Outlook demo...
📧 SMTP: Outlook (smtp-mail.outlook.com:587)
🎯 Target: d3m01231@outlook.com
🔐 Phishing Accounts: 2 accounts
   - phishing_testt1@outlook.com
   - phishing_testt2@outlook.com

[1/10] Sending: URGENT: Your PayPal Account Has Been Limited...
  📤 From: phishing_testt1@outlook.com
  ✓ Sent from phishing_testt1@outlook.com

[2/10] Sending: Your Amazon Order #4829-3847 Has Been Shipped...
  📤 From: phishing_testt2@outlook.com
  ✓ Sent from phishing_testt2@outlook.com

...

============================================================
📊 Summary:
  ✓ Sent: 10
  ✗ Failed: 0

🌐 View emails in Outlook: https://outlook.live.com
   Login as: d3m01231@outlook.com
🎯 Next: PhishTrap will auto-sync within 60 seconds!
   Dashboard: http://localhost:5000
============================================================
```

---

## 🔧 **Troubleshooting**

### **Authentication Failed**
```
❌ Authentication failed for phishing_testt1@outlook.com
```

**Solution:** Check your password in environment variables

### **Connection Refused**
```
❌ Error sending email: [Errno 111] Connection refused
```

**Solution:** Check internet connection and Outlook SMTP access

### **Missing Passwords**
```
❌ Error: Outlook mode requires passwords for phishing accounts
```

**Solution:** Set environment variables:
```bash
export OUTLOOK_PHISH1_PASSWORD='your_password'
export OUTLOOK_PHISH2_PASSWORD='your_password'
```

---

## 🎉 **Quick Start (Copy-Paste)**

```bash
# Set passwords (replace with your actual passwords)
export OUTLOOK_PHISH1_PASSWORD='YourPassword1'
export OUTLOOK_PHISH2_PASSWORD='YourPassword2'

# Generate 10 phishing emails
cd /home/osboxes/phishtrap/scripts
python3 generate_phishing_emails.py --mode outlook --count 10

# Watch PhishTrap dashboard auto-update!
# http://localhost:5000
```

---

**Your phishing test emails will appear in the dashboard within 60 seconds!** 🚀
