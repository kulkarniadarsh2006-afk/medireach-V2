# Render Deployment Guide - MediReach AI v2

This guide outlines the steps to deploy the MediReach AI Flask application to **Render** using either the manual dashboard configuration or the infrastructure-as-code Blueprint (`render.yaml`).

---

## 1. Quick Reference Configuration

To deploy successfully on Render, configure the service with these settings:

| Setting | Value |
| :--- | :--- |
| **Service Type** | Web Service |
| **Runtime** | Python |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn --worker-class eventlet -w 1 app:app` |

### Required Environment Variables

Configure the following environment variables in the Render Dashboard:

| Variable Name | Description | Example Value |
| :--- | :--- | :--- |
| `SUPABASE_URL` | The REST API endpoint of your Supabase project. | `https://fhzicqsekyccqknjwmuc.supabase.co` |
| `SUPABASE_ANON_KEY` | The client API key (anon key) for your Supabase project. | `sb_publishable_OLXix_wLaKB7g1CoXF8FNg...` |

---

## 2. Deployment Methods

### Method A: Deploying via Blueprint (Recommended)

MediReach v2 contains a preconfigured [render.yaml](file:///C:/Users/DELL/.gemini/antigravity/scratch/medireach-v2/render.yaml) file. Render can use this file to configure and launch your service automatically.

1. Push your repository to GitHub or GitLab.
2. Go to the [Render Dashboard](https://dashboard.render.com).
3. Click **New** (top right) and select **Blueprint**.
4. Connect your code repository.
5. Render will automatically parse `render.yaml` and prompt you for the missing environment variable values (`SUPABASE_URL` and `SUPABASE_ANON_KEY`).
6. Input the values and click **Apply**.

---

### Method B: Manual Web Service Creation

If you prefer to configure the service manually through the Render UI:

1. Go to the [Render Dashboard](https://dashboard.render.com).
2. Click **New** and select **Web Service**.
3. Connect your repository.
4. Set the following fields:
   - **Name**: `medireach-ai`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --worker-class eventlet -w 1 app:app`
5. Expand the **Advanced** section.
6. Click **Add Environment Variable** and enter:
   - Key: `SUPABASE_URL` | Value: *Your Supabase REST API URL*
   - Key: `SUPABASE_ANON_KEY` | Value: *Your Supabase anonymous key*
7. Click **Create Web Service**.

---

## 3. Architecture & Deployment Notes

- **WebSocket Support**: Because MediReach uses `Flask-SocketIO` to stream real-time updates to the dashboard, it requires an asynchronous WSGI server. This is why the start command uses `gunicorn` with the `--worker-class eventlet` worker.
- **Single Process Constraint**: The start command specifies `-w 1` (a single worker process). This is critical because the live-event simulation runs as a background thread inside the Flask process. Using multiple worker processes would duplicate this background thread, leading to out-of-sync WebSocket streams and redundant database operations.
- **Supabase Connectivity**: The application validates connection credentials on startup. If `SUPABASE_URL` or `SUPABASE_ANON_KEY` is missing or incorrect, the service will fail to start.
