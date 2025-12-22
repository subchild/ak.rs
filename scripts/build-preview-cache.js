#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.join(__dirname, "..");
const HTML_PATH = path.join(ROOT, "2025faves", "index.html");
const OUTPUT_PATH = path.join(ROOT, "2025faves", "preview-cache.json");

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const fetchJsonWithRetry = async (url, retries = 3, delayMs = 500) => {
  const response = await fetch(url);
  if (response.ok) {
    return response.json();
  }
  if (retries <= 0) {
    throw new Error(`HTTP ${response.status}`);
  }
  await delay(delayMs);
  return fetchJsonWithRetry(url, retries - 1, delayMs * 2);
};

const buildPreviewKey = (track) =>
  `${track.artist}||${track.title}`.toLowerCase();

const loadTracksByCategory = () => {
  const html = fs.readFileSync(HTML_PATH, "utf8");
  const match = html.match(
    /const tracksByCategory = ([\s\S]*?);\n\s*const defaultClipStart/
  );
  if (!match) {
    throw new Error("Could not locate tracksByCategory in index.html");
  }
  return vm.runInNewContext(`(${match[1]})`, {});
};

const buildApiUrl = (track) => {
  if (track.appleId) {
    return `https://itunes.apple.com/lookup?id=${encodeURIComponent(
      track.appleId
    )}&entity=song`;
  }
  const query = `${track.title} ${track.artist}${track.album ? ` ${track.album}` : ""}`;
  return `https://itunes.apple.com/search?term=${encodeURIComponent(
    query
  )}&media=music&entity=song&limit=1`;
};

const main = async () => {
  const tracksByCategory = loadTracksByCategory();
  const allTracks = Object.values(tracksByCategory).flat();
  const items = {};

  for (const track of allTracks) {
    const key = buildPreviewKey(track);
    if (items[key]) {
      continue;
    }
    const apiUrl = buildApiUrl(track);
    try {
      const data = await fetchJsonWithRetry(apiUrl);
      const resolved = data && data.results && data.results[0];
      if (resolved) {
        items[key] = resolved;
      } else {
        console.warn(`No preview for ${track.artist} - ${track.title}`);
      }
    } catch (error) {
      console.warn(
        `Failed for ${track.artist} - ${track.title}: ${error.message}`
      );
    }
    await delay(350);
  }

  const payload = {
    generatedAt: new Date().toISOString(),
    items,
  };

  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(payload, null, 2));
  console.log(`Wrote ${Object.keys(items).length} items to ${OUTPUT_PATH}`);
};

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
