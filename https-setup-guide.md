# HTTPS Setup Guide — Django on AWS Elastic Beanstalk with GoDaddy Domain

**App:** Safety SaaS (Django + Gunicorn + Docker)
**AWS Service:** Elastic Beanstalk (Load-Balanced)
**Domain Registrar:** GoDaddy

---

## Overview of All Phases

| Phase | What | Where |
|-------|------|-------|
| 1 | Request free SSL certificate | AWS ACM |
| 2 | Validate certificate via DNS | GoDaddy |
| 3 | Attach SSL cert to Load Balancer | EB Console |
| 4 | HTTP → HTTPS redirect (nginx config) | Code (.ebextensions) |
| 5 | Update Django environment variables | EB Console |
| 6 | Point domain to EB Load Balancer | GoDaddy |
| 7 | Deploy and test | Terminal |

---

## Option A — Create New Load-Balanced EB Environment

> Do this first if your current EB environment is Single Instance (no Load Balancer).

### Step 1 — Note Down Current Environment Variables

Go to: **EB Console → Your current environment → Configuration → Software → Environment Properties**

Write down all variables:
```
SECRET_KEY=
DATABASE_URL=
DEBUG=False
ALLOWED_HOSTS=
BREVO_API_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_S3_REGION_NAME=
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
SITE_URL=
CSRF_TRUSTED_ORIGINS=
SECURE_SSL_REDIRECT=
```

### Step 2 — Create New EB Environment

1. AWS Console → Elastic Beanstalk → **Create environment**
2. Select **"Web server environment"** → Next

### Step 3 — Set Platform

| Field | Value |
|-------|-------|
| Platform | Python |
| Platform branch | Python 3.12 |
| Platform version | Latest recommended |

### Step 4 — Select Custom Configuration

- Choose **"Custom configuration"** (not default presets)

### Step 5 — Configure Capacity (Key Step)

**Capacity → Edit:**

| Field | Value |
|-------|-------|
| Environment type | **Load balanced** |
| Min instances | 1 |
| Max instances | 1 |
| Instance type | t3.micro |

Click **Save**

### Step 6 — Configure Load Balancer

**Load balancer → Edit:**

| Field | Value |
|-------|-------|
| Load balancer type | **Application Load Balancer** |
| Listener Port 80 | HTTP — keep it |

> Leave HTTPS (443) for now — add it after ACM certificate is issued.

Click **Save**

### Step 7 — Add Environment Variables

**Software → Edit → Environment Properties:**

| Key | Value |
|-----|-------|
| `ALLOWED_HOSTS` | `yourdomain.com www.yourdomain.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://yourdomain.com,https://www.yourdomain.com` |
| `SITE_URL` | `https://yourdomain.com` |
| `SECURE_SSL_REDIRECT` | `True` |
| `DEBUG` | `False` |

Plus all variables from Step 1.

### Step 8 — Create the Environment

Click **"Create environment"** — takes 5–10 minutes.

### Step 9 — Verify App Works on HTTP First

Open the EB environment URL and confirm app loads:
```
http://myapp-new.ap-south-1.elasticbeanstalk.com
```

### Step 10 — Deploy Latest Code

```bash
source D:/venev1/scripts/activate
cd D:/safety-obs-workpermit-saas/safety-saas-claude

eb use <your-new-environment-name>
eb deploy
```

---

## Phase 1 — Get a Free SSL Certificate (AWS ACM)

1. AWS Console → **Certificate Manager (ACM)**
   - Must be in the **same region** as your EB app (e.g. `ap-south-1`)

2. Click **"Request a certificate"** → **"Request a public certificate"**

3. Enter domain names:
   ```
   yourdomain.com
   www.yourdomain.com
   ```

4. Choose **DNS validation** → Click **Request**

5. Copy the CNAME records shown (Name and Value) — needed for Phase 2.

---

## Phase 2 — Validate Certificate via GoDaddy DNS

1. GoDaddy → My Products → **DNS** for your domain

2. Add the 2 CNAME records from ACM:

   | Type | Name | Value |
   |------|------|-------|
   | CNAME | `_abc123` | `_xyz456.acm-validations.aws.` |
   | CNAME | `_abc123.www` | `_xyz456.acm-validations.aws.` |

   > Remove the domain suffix from the Name — GoDaddy adds it automatically.

3. Wait **5–30 minutes** → ACM status changes to **"Issued"**

---

## Phase 3 — Attach SSL to EB Load Balancer

1. EB Console → Your Environment → **Configuration → Load balancer → Edit**

2. Under **Listeners**, add a new listener:

   | Field | Value |
   |-------|-------|
   | Port | 443 |
   | Protocol | HTTPS |
   | SSL Certificate | Select the cert created in Phase 1 |

3. Keep the existing HTTP (port 80) listener.

4. Click **Apply** — EB updates in 5–10 min.

---

## Phase 4 — HTTP → HTTPS Redirect (Already Done in Code)

File already created at:
```
.ebextensions/https-redirect.config
```

This configures nginx to issue a 301 redirect for all HTTP requests.

---

## Phase 5 — Django Settings Already Updated

`settings.py` already has:
```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

This tells Django to trust the HTTPS header forwarded by the ALB.

---

## Phase 6 — Point GoDaddy Domain to EB Load Balancer

1. EB Console → Your Environment → copy the **Environment URL**
   ```
   myapp.ap-south-1.elasticbeanstalk.com
   ```

2. GoDaddy → DNS → Add records:

   | Type | Name | Value | TTL |
   |------|------|-------|-----|
   | CNAME | `www` | `myapp.ap-south-1.elasticbeanstalk.com` | 600 |
   | CNAME | `@` | `myapp.ap-south-1.elasticbeanstalk.com` | 600 |

   > If `@` (root domain) doesn't allow CNAME in GoDaddy, use:
   > **Forwarding** → redirect `yourdomain.com` → `https://www.yourdomain.com`

---

## Phase 7 — Deploy and Test

```bash
source D:/venev1/scripts/activate
cd D:/safety-obs-workpermit-saas/safety-saas-claude

eb deploy
```

Test with curl:
```bash
# Should return 301 redirect to HTTPS
curl -I http://yourdomain.com

# Should return 200 OK
curl -I https://yourdomain.com
```

Or simply open your browser and visit `http://yourdomain.com` — it should automatically redirect to `https://yourdomain.com` with a padlock icon.

---

## Checklist

- [ ] New Load-Balanced EB environment created
- [ ] App verified working on HTTP (EB URL)
- [ ] ACM certificate requested
- [ ] GoDaddy CNAME records added for ACM validation
- [ ] ACM certificate status = **Issued**
- [ ] HTTPS listener (port 443) added to EB Load Balancer with ACM cert
- [ ] GoDaddy DNS pointed to EB environment URL
- [ ] `eb deploy` run with latest code
- [ ] `http://yourdomain.com` redirects to `https://yourdomain.com`
- [ ] Padlock icon visible in browser
- [ ] Old Single Instance EB environment terminated

---

## Important Notes

- **ACM certificate is FREE** — you only pay for the Load Balancer (~$16-20/month)
- **HSTS is enabled** — after HTTPS is confirmed, browsers remember HTTPS-only for 1 year
- **DNS propagation** can take up to 48 hours (usually 15–30 min)
- **Old environment** — keep it running until new environment + HTTPS is fully verified, then terminate it
- **eb use** — always confirm you are deploying to the correct environment with `eb status`

---

## Files Modified in This Project

| File | Change |
|------|--------|
| `safety_inspection/settings.py` | Added `SECURE_PROXY_SSL_HEADER` |
| `.ebextensions/https-redirect.config` | New file — nginx HTTP → HTTPS redirect |
