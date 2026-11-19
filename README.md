# ClipFetch

A single-service media-link helper. The responsive frontend and FastAPI backend run together in one Docker web service. `yt-dlp` handles supported public media URLs; FFmpeg is included for merging formats.

## Deploy on Render (free tier)

1. Put this project in a GitHub repository.
2. In Render, choose **New + → Blueprint** and connect that repository.
3. Render detects `render.yaml`; review and create the `clipfetch` web service.
4. Wait for the first Docker build to finish, then open the `onrender.com` URL shown on the service page.

The service uses Render's free instance. It may sleep after inactivity and take time to wake. Its filesystem is ephemeral: downloaded files can disappear after a restart or redeploy. The free instance has limited CPU/RAM, so large or long downloads may fail. This is a prototype, not reliable production hosting.

## Local Docker run

```bash
docker compose up -d --build
```

Open `http://localhost:8000`.

## Responsible use and limitations

- Use only media you own or are authorized to save, and comply with the source site's terms and applicable law.
- This app does not bypass DRM, login walls, paywalls, or other access controls.
- A 500 MB maximum file-size option is applied to downloads, but this is not a guarantee against every oversized or resource-intensive request.
- Before public production use, add robust SSRF protections, authentication, per-user rate limits, concurrency limits, monitoring, and reliable temporary-file cleanup.
- Render free storage is not persistent. Do not rely on it as permanent file hosting.
