// Render the website's evidence replay as a silent MP4. Never starts the factory.
// PLAYWRIGHT_MODULE=... BROWSER_EXECUTABLE=... node render-video.cjs PREVIEW_URL
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");
const { execFileSync } = require("node:child_process");

(async () => {
  const media = path.resolve(__dirname, "../public/media");
  const replayBytes = await fs.readFile(path.join(media, "recorded-run.json"));
  const replay = JSON.parse(replayBytes);
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), "forge-c-video-"));
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.BROWSER_EXECUTABLE,
  });
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
      deviceScaleFactor: 1,
    });
    await page.goto(process.argv[2], { waitUntil: "networkidle" });
    await page.addStyleTag({
      content: `
      [data-replay]{width:1280px!important;height:720px!important;border-radius:0!important;position:relative!important;border:0!important}
      [data-replay] .replay-top{padding:24px 36px!important;font-size:13px!important}
      [data-replay] .replay-body{padding:32px 36px!important}
      [data-replay] .replay-intro>strong{font-size:38px!important}
      [data-replay] .small-label{font-size:12px!important}
      [data-replay] .replay-intro>p{font-size:15px!important;margin-bottom:30px!important}
      [data-replay] .replay-station{padding:22px 14px!important}
      [data-replay] .replay-station>strong{font-size:15px!important;min-height:34px!important}
      [data-replay] .replay-station>span{font-size:13px!important}
      [data-replay] .replay-station>small{font-size:11px!important}
      [data-replay] .replay-event{margin-top:30px!important;min-height:120px!important;padding:24px!important}
      [data-replay] .replay-event>div{font-size:14px!important}
      [data-replay] .replay-event>p{font-size:15px!important}
      [data-replay] .replay-badge{font-size:13px!important}
      [data-replay] .replay-footer{font-size:11px!important;margin-top:26px!important}
      [data-replay] .replay-controls{display:none!important}
      [data-replay]::after{content:'RECORDED GATE-EVENT VISUALIZATION · TIME COMPRESSED · NOT A LIVE RUN';position:absolute;bottom:21px;left:36px;color:#a6b4bd;font:11px Consolas,monospace;letter-spacing:.08em}
    `,
    });
    await page.evaluate(() => {
      const replay = document.querySelector("[data-replay]");
      document.body.replaceChildren(replay);
      document.body.style.margin = "0";
    });
    const target = page.locator("[data-replay]");
    const frames = [];
    for (let i = 0; i < replay.events.length; i++) {
      await target.evaluate(
        (element, index) =>
          element.dispatchEvent(
            new CustomEvent("forge-replay-seek", { detail: index }),
          ),
        i,
      );
      await page.waitForTimeout(250);
      const frame = path.join(temp, `frame-${String(i).padStart(2, "0")}.png`);
      await target.screenshot({ path: frame, animations: "disabled" });
      frames.push(frame);
    }
    const list = frames.flatMap((frame) => [`file '${frame}'`, "duration 2.5"]);
    list.push(`file '${frames.at(-1)}'`);
    const concat = path.join(temp, "frames.txt");
    await fs.writeFile(concat, list.join("\n"));
    execFileSync("ffmpeg", [
      "-hide_banner",
      "-loglevel",
      "error",
      "-y",
      "-f",
      "concat",
      "-safe",
      "0",
      "-i",
      concat,
      "-t",
      "45",
      "-r",
      "24",
      "-c:v",
      "libx264",
      "-preset",
      "slow",
      "-crf",
      "21",
      "-pix_fmt",
      "yuv420p",
      "-movflags",
      "+faststart",
      path.join(temp, "workflow-replay.mp4"),
    ]);
    await fs.copyFile(
      path.join(temp, "workflow-replay.mp4"),
      path.join(media, "workflow-replay.mp4"),
    );
    await fs.copyFile(
      frames[7],
      path.join(media, "workflow-replay-poster.png"),
    );
    const sha = (data) =>
      crypto.createHash("sha256").update(data).digest("hex");
    await fs.writeFile(
      path.join(media, "video-provenance.json"),
      JSON.stringify(
        {
          description:
            "Rendered visualization of recorded gate events; not a live run or screen recording.",
          run_id: replay.run_id,
          duration_seconds: 45,
          dimensions: [1280, 720],
          replay_sha256: sha(replayBytes),
          video_sha256: sha(
            await fs.readFile(path.join(media, "workflow-replay.mp4")),
          ),
          event_count: replay.events.length,
          captions: "workflow-replay.vtt",
          source_hashes: replay.sources,
        },
        null,
        2,
      ) + "\n",
    );
    console.log(
      JSON.stringify({
        video: path.join(media, "workflow-replay.mp4"),
        events: replay.events.length,
        duration: 45,
      }),
    );
  } finally {
    await browser.close();
    await fs.rm(temp, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
